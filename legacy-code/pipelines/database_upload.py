from utils.database_context_manager import session_scope
from database import models 
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base
from pipelines.base import BasePipeline

class DatabasePipeline(BasePipeline):
    def __init__(self, settings=None):
        self.logger = logging.getLogger(__name__)
        self.logger.info("DatabasePipeline: __init__ called")
        super().__init__(settings)
        self.engine = None
        self.session_factory = None
        self.db_url = settings.get('DATABASE_URL') if settings else None
        
    def open_spider(self, spider):
        self.logger.info("DatabasePipeline open_spider called") 
        # Initialize database connection when spider starts
        self.spider = spider
        self.initialize()
        
    
    def initialize(self, create_tables=True):
        """Initialize database connection and create tables if needed"""
        try:
            # Create engine and session factory
            self.engine = create_engine(self.db_url)
            self.session_factory = sessionmaker(bind=self.engine)
            
            # Create tables if needed
            if create_tables:
                Base.metadata.create_all(self.engine)
                
            self.logger.info("Database connection initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            return False
        
    def process_item(self, item, spider):
        # Check if we received a batch of valid items
        valid_items = []

        # The first validated item has an additional field called _valid_batch which contains a list of all validated items. 
        # This allows batch processing while working within Scrapy's one-item-at-a-time pipeline architecture.
        
        self.logger.info(f"process_item called with item type: {type(item)}")
        
        if item is not None and '_valid_batch' in item:
            # Extract the batch of valid items
            valid_items = item.get('_valid_batch', [])
            self.logger.info(f"Received batch of {len(valid_items)} valid items to save")
            
            # Remove the metadata field to avoid saving it to the database
            if hasattr(item, 'pop'):
                item.pop('_valid_batch', None)
        else:
            # If no batch, just process this single item
            valid_items = [item]
            self.logger.info("Received single item to save")
        
        # Process all items using the helper function
        self.logger.info(f"Creating session with factory: {self.session_factory}")
        try:
            with session_scope() as session:
                self.logger.info("Session created successfully")
                try:
                    for i, valid_item in enumerate(valid_items):
                        self.logger.info(f"Processing item {i+1}/{len(valid_items)}")
                        if valid_item is None:
                            self.logger.warning(f"Item {i+1} is None, skipping")
                            continue
                        
                        try:
                            # Get model data with flush instructions
                            self.logger.info(f"Deconstructing item {i+1} with reference_id: {valid_item.get('reference_id', 'unknown')}")
                            model_data = self.deconstruct_validated_data(valid_item)
                            
                            # Add and flush primary models first
                            self.logger.info(f"Adding {len(model_data['primary_models'])} primary models")
                            for model in model_data['primary_models']:
                                session.add(model)
                            session.flush()  # Critical - ensures primary keys are generated
                            self.logger.info("Primary models flushed successfully")
                            
                            # Add and flush secondary models
                            self.logger.info(f"Adding {len(model_data['secondary_models'])} secondary models")
                            for model in model_data['secondary_models']:
                                session.add(model)
                            session.flush()  # Critical - ensures foreign keys are available
                            self.logger.info("Secondary models flushed successfully")
                            
                            # Add tertiary models last
                            self.logger.info(f"Adding {len(model_data['tertiary_models'])} tertiary models")
                            for model in model_data['tertiary_models']:
                                session.add(model)
                            self.logger.info("All models added successfully for item")
                            
                        except Exception as e:
                            # Log the specific item that failed and continue with next item
                            self.logger.error(f"Failed to process item {valid_item.get('reference_id', 'unknown')}: {str(e)}", exc_info=True)
                            continue
                    
                    # Commit everything as a single transaction
                    self.logger.info("Committing all changes to database")
                    session.commit()
                    self.logger.info("Successfully committed all changes to database")
                    
                except Exception as e:
                    session.rollback()
                    self.logger.error(f"Database error during batch processing: {str(e)}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Failed to create database session: {str(e)}", exc_info=True)
                    
        self.logger.info("Returning from process_item")
        return item

    def deconstruct_validated_data(self, validated_item):
        """
        Convert a validated item into database model instances with proper relationship hierarchy
        """
        # Create empty lists for each level of models
        primary_models = []
        secondary_models = []
        tertiary_models = []
        
        # Step 1: Create primary/parent model - ProjectParticulars
        project = models.ProjectParticulars(
            reference_id=validated_item.get('reference_id'),
            application_reference=validated_item.get('application_reference'),
            site_address=validated_item.get('site_address'),
            proposal=validated_item.get('proposal'),
            council_name=validated_item.get('council_name'),
            status=validated_item.get('status'),
            decision=validated_item.get('decision'),
            site_address_line1=validated_item.get('site_address_line1'),
            site_address_line2=validated_item.get('site_address_line2'),
            site_address_town=validated_item.get('site_address_town'),
            site_address_city=validated_item.get('site_address_city'),
            site_address_county=validated_item.get('site_address_county'),
            site_address_country=validated_item.get('site_address_country'),
            site_address_postcode=validated_item.get('site_address_postcode'),
            residential_units=validated_item.get('residential_units'),
            commercial_units=validated_item.get('commercial_units'),
            estimated_value=validated_item.get('estimated_value'),
            householder_type=validated_item.get('householder_type'),
            proposal_category=validated_item.get('proposal_category'),
            proposal_is_householder=validated_item.get('proposal_is_householder'),
            proposal_is_conversion=validated_item.get('proposal_is_conversion'),
            proposal_conversion_type=validated_item.get('proposal_conversion_type'),
            parish=validated_item.get('parish'),
            ward=validated_item.get('ward'),
            application_url=validated_item.get('application_url')
        )
        primary_models.append(project)
        
        # Step 2: Create secondary models that depend on primary models
        
        # ProjectDates - secondary model
        if any(key in validated_item for key in ['registration_date', 'decision_date', 'expiry_date']):
            dates = models.ProjectDates(
                project=project,
                reference_id=project.reference_id,
                valid_from=validated_item.get('valid_from'),
                registration_date=validated_item.get('registration_date'),
                decision_date=validated_item.get('decision_date'),
                expiry_date=validated_item.get('expiry_date'),
                consultation_start_date=validated_item.get('consultation_start_date'),
                consultation_expiry_date=validated_item.get('consultation_expiry_date'),
                target_decision_date=validated_item.get('target_decision_date'),
                statutory_expiry_date=validated_item.get('statutory_expiry_date'),
                dispatch_date=validated_item.get('dispatch_date'),
                decision_due_date=validated_item.get('decision_due_date'),
                decision_expiry_date=validated_item.get('decision_expiry_date'),
                site_notice_date=validated_item.get('site_notice_date'),
                publicity_end_date=validated_item.get('publicity_end_date'),
                advert_expiry_date=validated_item.get('advert_expiry_date'),
                extended_target_decision_date=validated_item.get('extended_target_decision_date'),
                committee_date=validated_item.get('committee_date'),
                received_date=validated_item.get('received_date'),
                site_visit_date=validated_item.get('site_visit_date'),
                planning_perfromance_agreement_due_date=validated_item.get('planning_perfromance_agreement_due_date'),
                actual_committee_date=validated_item.get('actual_committee_date'),
                appeal_external_decision_date=validated_item.get('appeal_external_decision_date'),
                final_grant_date=validated_item.get('final_grant_date'),
                extension_date=validated_item.get('extension_date'),
                appeal_lodged_date=validated_item.get('appeal_lodged_date'),
                appeal_notify_date=validated_item.get('appeal_notify_date'),
                submision_expiry_date=validated_item.get('submision_expiry_date'),
                application_date=validated_item.get('application_date'),
                press_notice_start_date=validated_item.get('press_notice_start_date')
            )
            secondary_models.append(dates)
        
        # ProjectMiscellaneous - secondary model
        if any(key in validated_item for key in ['case_officer_name', 'application_type', 'development_type']):
            misc_data = models.ProjectMiscellaneous(
                project=project,
                reference_id=project.reference_id,
                environmental_assessment_required=validated_item.get('environmental_assessment_required'),
                case_officer_name=validated_item.get('case_officer_name'),
                determination_level=validated_item.get('determination_level'),
                development_type=validated_item.get('development_type'),
                application_type=validated_item.get('application_type'),
                application_type_id=validated_item.get('application_type_id'),
                division=validated_item.get('division'),
                existing_land_use=validated_item.get('existing_land_use'),
                proposed_land_use=validated_item.get('proposed_land_use'),
                location_coordinates=validated_item.get('location_coordinates'),
                expected_decision_level=validated_item.get('expected_decision_level'),
                listed_building_grade=validated_item.get('listed_building_grade'),
                extension_of_time=validated_item.get('extension_of_time'),
                planning_performance_agreement=validated_item.get('planning_performance_agreement'),
                appeal_reference=validated_item.get('appeal_reference'),
                easting=validated_item.get('easting'),
                northing=validated_item.get('northing'),
                appeal_type=validated_item.get('appeal_type'),
                development_category=validated_item.get('development_category')
            )
            secondary_models.append(misc_data)
        
        # CompanyDetails - secondary models (one for applicant, one for agent if they exist)
        applicant_company = None
        agent_company = None
        
        # Process applicant company if data exists
        if any(key.startswith('applicant_company') for key in validated_item.keys()) or validated_item.get('company_name'):
            # Extract applicant company data
            applicant_company = models.CompanyDetails(
                project=project,
                reference_id=project.reference_id,
                company_type='applicant',
                company_name=validated_item.get('applicant_company_name', validated_item.get('company_name')),
                company_reg_name=validated_item.get('applicant_company_reg_name'),
                company_reg_number=validated_item.get('applicant_company_reg_number'),
                company_reg_address_line1=validated_item.get('applicant_company_reg_address_line1'),
                company_reg_address_line2=validated_item.get('applicant_company_reg_address_line2'),
                company_reg_city=validated_item.get('applicant_company_reg_city'),
                company_reg_county=validated_item.get('applicant_company_reg_county'),
                company_reg_country=validated_item.get('applicant_company_reg_country'),
                company_reg_postcode=validated_item.get('applicant_company_reg_postcode'),
                company_reg_type=validated_item.get('applicant_company_reg_type')
            )
            secondary_models.append(applicant_company)
            
        # Process agent company if data exists
        if any(key.startswith('agent_company') for key in validated_item.keys()):
            # Extract agent company data
            agent_company = models.CompanyDetails(
                project=project,
                reference_id=project.reference_id,
                company_type='agent',
                company_name=validated_item.get('agent_company_name'),
                company_reg_name=validated_item.get('agent_company_reg_name'),
                company_reg_number=validated_item.get('agent_company_reg_number'),
                company_reg_address_line1=validated_item.get('agent_company_reg_address_line1'),
                company_reg_address_line2=validated_item.get('agent_company_reg_address_line2'),
                company_reg_city=validated_item.get('agent_company_reg_city'),
                company_reg_county=validated_item.get('agent_company_reg_county'),
                company_reg_country=validated_item.get('agent_company_reg_country'),
                company_reg_postcode=validated_item.get('agent_company_reg_postcode'),
                company_reg_type=validated_item.get('agent_company_reg_type')
            )
            secondary_models.append(agent_company)
        
        # For backwards compatibility, check the original 'company' field
        if validated_item.get('company') and not applicant_company and not agent_company:
            company_data = validated_item.get('company', {})
            if isinstance(company_data, str):
                company_data = {'company_name': company_data}
                
            # Determine if this is an applicant or agent company
            company_type = company_data.get('company_type', 'applicant')
            company = models.CompanyDetails(
                project=project,
                reference_id=project.reference_id,
                company_type=company_type,
                company_name=company_data.get('company_name', validated_item.get('company_name')),
                company_reg_name=company_data.get('company_reg_name'),
                company_reg_number=company_data.get('company_reg_number'),
                company_reg_address_line1=company_data.get('company_reg_address_line1'),
                company_reg_address_line2=company_data.get('company_reg_address_line2'),
                company_reg_city=company_data.get('company_reg_city'),
                company_reg_county=company_data.get('company_reg_county'),
                company_reg_country=company_data.get('company_reg_country'),
                company_reg_postcode=company_data.get('company_reg_postcode'),
                company_reg_type=company_data.get('company_reg_type')
            )
            secondary_models.append(company)
            
            # Set the appropriate company variable based on type
            if company_type == 'applicant':
                applicant_company = company
            else:
                agent_company = company
        
        # Step 3: Create tertiary models that depend on secondary models
        
        # ApplicantDetails - tertiary model
        # Check if we have any applicant fields with the prefix
        if any(key.startswith('applicant_') and not key.startswith('applicant_company') for key in validated_item.keys()):
            applicant = models.ApplicantDetails(
                project=project,
                reference_id=project.reference_id,
                company=applicant_company,
                company_id=applicant_company.id if applicant_company else None,
                name_first=validated_item.get('applicant_name_first'),
                name_middle=validated_item.get('applicant_name_middle'),
                name_last=validated_item.get('applicant_name_last'),
                name_title=validated_item.get('applicant_name_title'),
                name_suffix=validated_item.get('applicant_name_suffix'),
                name_gender=validated_item.get('applicant_name_gender'),
                name_salutation=validated_item.get('applicant_name_salutation'),
                address_line1=validated_item.get('applicant_address_line1'),
                address_line2=validated_item.get('applicant_address_line2'),
                address_town=validated_item.get('applicant_address_town'),
                address_city=validated_item.get('applicant_address_city'),
                address_county=validated_item.get('applicant_address_county'),
                address_country=validated_item.get('applicant_address_country'),
                address_postcode=validated_item.get('applicant_address_postcode'),
                applicant_surname=validated_item.get('applicant_surname')
            )
            tertiary_models.append(applicant)

        
        # AgentDetails - tertiary model
        # Check if we have any agent fields with the prefix
        if any(key.startswith('agent_') and not key.startswith('agent_company') for key in validated_item.keys()):
            agent = models.AgentDetails(
                project=project,
                reference_id=project.reference_id,
                company=agent_company,
                company_id=agent_company.id if agent_company else None,
                name_first=validated_item.get('agent_name_first'),
                name_middle=validated_item.get('agent_name_middle'),
                name_last=validated_item.get('agent_name_last'),
                name_title=validated_item.get('agent_name_title'),
                name_suffix=validated_item.get('agent_name_suffix'),
                name_gender=validated_item.get('agent_name_gender'),
                name_salutation=validated_item.get('agent_name_salutation'),
                address_line1=validated_item.get('agent_address_line1'),
                address_line2=validated_item.get('agent_address_line2'),
                address_town=validated_item.get('agent_address_town'),
                address_city=validated_item.get('agent_address_city'),
                address_county=validated_item.get('agent_address_county'),
                address_country=validated_item.get('agent_address_country'),
                address_postcode=validated_item.get('agent_address_postcode'),
                phone=validated_item.get('agent_phone'),
                agent_initials=validated_item.get('agent_initials'),
                agent_title=validated_item.get('agent_title')
            )
            tertiary_models.append(agent)
    
        # ArchitectDetails - keep existing code for now unless architect data is also prefixed
        # ... existing architect code ...
                
        # Return all models organized by dependency hierarchy
        return {
            'primary_models': primary_models,
            'secondary_models': secondary_models,
            'tertiary_models': tertiary_models
        }