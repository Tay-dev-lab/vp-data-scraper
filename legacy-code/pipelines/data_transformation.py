import pandas as pd
from datetime import datetime
import re
from itemadapter import ItemAdapter
from .base import BasePipeline
from .name_transformation import NameProcessor
from .address_transformation import AddressProcessor
from .proposal_categoriser import ProposalCategoriser
from .util_transformations import (
    standardize_date, standardize_phone_number, clean_email_address,
    clean_text_field, standardize_postcode, standardize_numeric
)
from .company_lookup_integration import CompanyLookupIntegration
from dotenv import load_dotenv

# Load environment variables at module level
load_dotenv()

class DataTransformationPipeline(BasePipeline):
    """
    Pipeline stage 1: Data transformation and cleanup using pandas
    
    Responsibilities:
    - Collect items in a buffer
    - Process items in batches with pandas for efficiency
    - Clean and standardize data
    - Pass transformed data to the next pipeline
    """
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self.batch_size = settings.get('BATCH_SIZE', 100) if settings else 100
        self.items_buffer = []
        self.name_processor = NameProcessor()
        self.address_processor = AddressProcessor()
        self.proposal_categoriser = ProposalCategoriser()
        
        # Initialize company lookup integration using environment variables only
        self.logger.info("Initializing CompanyLookupIntegration")
        self.company_lookup = CompanyLookupIntegration()  # No db_params - will use env vars
        
    def process_item(self, item, spider):
        # Add item to buffer
        adapter = ItemAdapter(item)
        app_ref = adapter.get('application_reference', 'unknown')
        self.logger.debug(f"Buffering item {app_ref} (buffer size: {len(self.items_buffer)+1}/{self.batch_size})")
        self.items_buffer.append(dict(ItemAdapter(item)))
        
        # Process batch if buffer size reaches threshold
        if len(self.items_buffer) >= self.batch_size:
            self.logger.info(f"Buffer full ({self.batch_size} items) - processing batch now")
            return self._process_batch()
            
        # Don't pass item to next pipeline yet - buffer it until we have enough items
        # Return None to signal that this item is being handled asynchronously
        self.logger.debug(f"Item {app_ref} buffered, waiting for more items to reach batch size")
        return None
    
    def close_spider(self, spider):
        # Process any remaining items
        if self.items_buffer:
            self.logger.info(f"Spider closing - processing remaining {len(self.items_buffer)} buffered items")
            self._process_batch()
        super().close_spider(spider)
    
    def _process_batch(self):
        """Transform a batch of items using pandas"""
        self.logger.info(f"Transforming batch of {len(self.items_buffer)} items")
        
        # Create DataFrame from items
        df = pd.DataFrame(self.items_buffer)
        
        # Apply transformations
        transformed_df = self._transform_data(df)
        
        # Save to CSV for inspection
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transformed_df.to_csv(f"transformed_data_{timestamp}.csv", index=False)
        self.logger.info(f"Saved transformed data to transformed_data_{timestamp}.csv")
        
        # Convert back to list of dicts for next pipeline
        transformed_items = transformed_df.to_dict('records')
        
        # Update stats
        self.update_stats('items_processed', len(transformed_items))
        
        # Clear buffer
        self.items_buffer = []
        
        # Pass first item to next pipeline with metadata for the rest
        first_item = transformed_items[0]
        first_item['_batch_items'] = transformed_items
        
        return first_item
    
    def _transform_data(self, df):
        """Apply pandas transformations to clean and prepare data"""
        # Log original columns at the start of processing
        self.logger.info("==== COLUMNS BEFORE PROCESSING ====")
        self.logger.info(f"DataFrame shape: {df.shape}")
        for col in sorted(df.columns):
            non_null = df[col].count()
            total = len(df)
            null_percentage = ((total - non_null) / total) * 100 if total > 0 else 0
            self.logger.info(f"  - {col}: {non_null}/{total} non-null values ({null_percentage:.1f}% empty)")
        self.logger.info("====================================")
        
        # Make a copy to avoid modifying the original
        df_clean = df.copy()
        
        # Clean string fields
        string_cols = df_clean.select_dtypes(include=['object']).columns
        for col in string_cols:
            df_clean[col] = df_clean[col].apply(
                lambda x: clean_text_field(x)
            )
        
        # # Process regular name fields (case_officer)
        # name_columns = ['agent_name' , 'applicant_name']
        # for col in name_columns:
        #     if col in df_clean.columns:
        #         # Split the name into components
        #         name_parts = df_clean[col].apply(self.name_processor.parse_name)
                
        #         # Create new columns for each name component
        #         df_clean[f'{col}_first'] = name_parts.apply(lambda x: x.get('first'))
        #         df_clean[f'{col}_middle'] = name_parts.apply(lambda x: x.get('middle'))
        #         df_clean[f'{col}_last'] = name_parts.apply(lambda x: x.get('last'))
        #         df_clean[f'{col}_title'] = name_parts.apply(lambda x: x.get('title'))
        #         df_clean[f'{col}_suffix'] = name_parts.apply(lambda x: x.get('suffix'))
                
        #         # Apply title case to name components
        #         for name_part in [f'{col}_first', f'{col}_middle', f'{col}_last']:
        #             df_clean[name_part] = df_clean[name_part].apply(
        #                 lambda x: self.name_processor.capitalize_name_part(x, is_last_name=name_part.endswith('_last'))
        #             )
                
        #         # Also title case the original name field
        #         df_clean[col] = df_clean[col].apply(
        #             lambda x: self.name_processor.capitalize_name_part(x, is_last_name=True)
        #         )
                
        #         # Add gender and salutation
        #         df_clean[f'{col}_gender'] = df_clean[f'{col}_first'].apply(self.name_processor.detect_gender)
        #         df_clean[f'{col}_salutation'] = df_clean.apply(
        #             lambda row: self.name_processor.create_salutation(
        #                 row[f'{col}_title'],
        #                 row[f'{col}_first'], 
        #                 row[f'{col}_last'], 
        #                 row[f'{col}_gender']
        #             ), axis=1
        #         )
        
        # Special processing for agent_name field with company detection
        if 'agent_name' in df_clean.columns:
            self.logger.info("Processing agent names with company name extraction")
            
            # Use our enhanced method that separates companies from people
            processed_agent_names = df_clean['agent_name'].apply(
                lambda name: self.name_processor.process_name_for_database(name, role='agent')
            )
            
            # Extract company names to a separate column
            df_clean['agent_company_name'] = processed_agent_names.apply(
                lambda x: x.get('agent_company_name')
            )
            
            # Extract person name components to separate columns
            df_clean['agent_name_first'] = processed_agent_names.apply(lambda x: x.get('first_name'))
            df_clean['agent_name_middle'] = processed_agent_names.apply(lambda x: x.get('middle_name'))
            df_clean['agent_name_last'] = processed_agent_names.apply(lambda x: x.get('last_name'))
            df_clean['agent_name_title'] = processed_agent_names.apply(lambda x: x.get('title'))
            df_clean['agent_name_suffix'] = processed_agent_names.apply(lambda x: x.get('suffix'))
            
            # Add gender and salutation
            df_clean['agent_name_gender'] = processed_agent_names.apply(lambda x: x.get('gender'))
            df_clean['agent_name_salutation'] = processed_agent_names.apply(lambda x: x.get('agent_salutation'))
            
            # Apply title case to name components (if they exist)
            for name_part in ['agent_name_first', 'agent_name_middle', 'agent_name_last']:
                df_clean[name_part] = df_clean[name_part].apply(
                    lambda x: self.name_processor.capitalize_name_part(
                        x, is_last_name=name_part.endswith('_last')
                    ) if x is not None else x
                )
            
            # Log statistics
            company_count = df_clean['agent_company_name'].notna().sum()
            self.logger.info(f"Extracted {company_count} company names from agent_name field")
        
        # Special processing for applicant_name field with company detection
        if 'applicant_name' in df_clean.columns:
            self.logger.info("Processing applicant names with company name extraction")
            
            # Use our enhanced method that separates companies from people
            processed_applicant_names = df_clean['applicant_name'].apply(
                lambda name: self.name_processor.process_name_for_database(name, role='applicant')
            )
            
            # Extract company names to a separate column
            df_clean['applicant_company_name'] = processed_applicant_names.apply(
                lambda x: x.get('applicant_company_name')
            )
            
            # Extract person name components to separate columns
            df_clean['applicant_name_first'] = processed_applicant_names.apply(lambda x: x.get('first_name'))
            df_clean['applicant_name_middle'] = processed_applicant_names.apply(lambda x: x.get('middle_name'))
            df_clean['applicant_name_last'] = processed_applicant_names.apply(lambda x: x.get('last_name'))
            df_clean['applicant_name_title'] = processed_applicant_names.apply(lambda x: x.get('title'))
            df_clean['applicant_name_suffix'] = processed_applicant_names.apply(lambda x: x.get('suffix'))
            
            # Add gender and salutation
            df_clean['applicant_name_gender'] = processed_applicant_names.apply(lambda x: x.get('gender'))
            df_clean['applicant_name_salutation'] = processed_applicant_names.apply(lambda x: x.get('agent_salutation'))
            
            # Apply title case to name components (if they exist)
            for name_part in ['applicant_name_first', 'applicant_name_middle', 'applicant_name_last']:
                df_clean[name_part] = df_clean[name_part].apply(
                    lambda x: self.name_processor.capitalize_name_part(
                        x, is_last_name=name_part.endswith('_last')
                    ) if x is not None else x
                )
            
            # Log statistics
            company_count = df_clean['applicant_company_name'].notna().sum()
            self.logger.info(f"Extracted {company_count} company names from applicant_name field")
        
        # Perform company lookup if enabled - add checks to avoid AttributeError
        if self.company_lookup and ('agent_company_name' in df_clean.columns or 'applicant_company_name' in df_clean.columns):
            self.logger.info("Performing company lookups against Companies House database")
            try:
                df_clean = self.company_lookup.process_dataframe(df_clean)
                self.logger.info("Company lookup processing completed successfully")
            except AttributeError as e:
                self.logger.error(f"Company lookup failed: {e}. Check class initialization.")
            except Exception as e:
                self.logger.error(f"Company lookup processing error: {e}")
        
        # Process address fields
        address_columns = ['applicant_address', 'agent_address', 'site_address']
        for col in address_columns:
            if col in df_clean.columns:
                # Process the address
                address_parts = df_clean[col].apply(self.address_processor.process_address)
                
                # Function to format address components according to our requirements
                def format_address_components(address_dict):
                    result = {
                        'address_line_1': None,
                        'address_line_2': None,
                        'post_town': None,
                        'city': None,
                        'county': None,
                        'country': None,
                        'postcode': None
                    }
                    
                    # Keep track of fields we've already used
                    used_fields = set()
                    
                    # PRIORITY 1: unit, level, or entrance for address_line_1
                    line1_parts = []
                    for field in ['unit', 'level', 'entrance']:
                        if field in address_dict:
                            line1_parts.append(address_dict[field])
                            used_fields.add(field)
                    
                    if line1_parts:
                        result['address_line_1'] = ' '.join(line1_parts)
                    
                    # PRIORITY 2: house, house_number, road
                    # If line1 is empty, use these for line1, otherwise use for line2
                    line_parts = []
                    for field in ['house', 'house_number', 'road']:
                        if field in address_dict and field not in used_fields:
                            line_parts.append(address_dict[field])
                            used_fields.add(field)
                    
                    if line_parts:
                        if not result['address_line_1']:
                            result['address_line_1'] = ' '.join(line_parts)
                        else:
                            result['address_line_2'] = ' '.join(line_parts)
                    
                    # PRIORITY 3: house_number and road (if not already used)
                    if not result['address_line_1']:
                        line_parts = []
                        for field in ['house_number', 'road']:
                            if field in address_dict and field not in used_fields:
                                line_parts.append(address_dict[field])
                                used_fields.add(field)
                        
                        if line_parts:
                            result['address_line_1'] = ' '.join(line_parts)
                    
                    # PRIORITY 4: just road (if not already used)
                    if 'road' in address_dict and 'road' not in used_fields:
                        if not result['address_line_1']:
                            result['address_line_1'] = address_dict['road']
                        elif not result['address_line_2']:
                            result['address_line_2'] = address_dict['road']
                    
                    # Map other address components according to requested logic
                    if 'suburb' in address_dict:
                        result['post_town'] = address_dict['suburb']
                    elif 'city_district' in address_dict:
                        result['post_town'] = address_dict['city_district']
                        
                    if 'city' in address_dict:
                        result['city'] = address_dict['city']
                        
                    if 'state_district' in address_dict:
                        result['county'] = address_dict['state_district']
                        
                    if 'state' in address_dict:
                        result['country'] = address_dict['state']
                    elif 'country' in address_dict:
                        result['country'] = address_dict['country']
                        
                    if 'postcode' in address_dict:
                        result['postcode'] = address_dict['postcode']
                        
                    return result
                
                # Apply the formatting function to each address
                formatted_addresses = address_parts.apply(format_address_components)
                
                # Create new columns with the formatted components
                df_clean[f'{col}_line1'] = formatted_addresses.apply(lambda x: x.get('address_line_1'))
                df_clean[f'{col}_line2'] = formatted_addresses.apply(lambda x: x.get('address_line_2'))
                df_clean[f'{col}_town'] = formatted_addresses.apply(lambda x: x.get('post_town'))
                df_clean[f'{col}_city'] = formatted_addresses.apply(lambda x: x.get('city'))
                df_clean[f'{col}_county'] = formatted_addresses.apply(lambda x: x.get('county'))
                df_clean[f'{col}_country'] = formatted_addresses.apply(lambda x: x.get('country'))
                df_clean[f'{col}_postcode'] = formatted_addresses.apply(lambda x: x.get('postcode'))
                
                # Standardize postcodes
                if f'{col}_postcode' in df_clean.columns:
                    df_clean[f'{col}_postcode'] = df_clean[f'{col}_postcode'].apply(standardize_postcode)
        
        # Process proposal fields for categorization
        proposal_columns = ['proposal', 'description', 'development_description']
        
        # Initialize default columns for residential and commercial units
        if 'residential_units' not in df_clean.columns:
            df_clean['residential_units'] = 0
        if 'commercial_units' not in df_clean.columns:
            df_clean['commercial_units'] = 0
        
        # Initialize estimated_value column
        df_clean['estimated_value'] = None
        
        # Create a dedicated householder_type column
        df_clean['householder_type'] = None
        
        for col in proposal_columns:
            if col in df_clean.columns:
                self.logger.info(f"Categorizing proposals from column: {col}")
                
                # Apply the proposal categorizer
                categorization = df_clean[col].apply(self.proposal_categoriser.categorize_proposal)
                
                # Extract categorization details into separate columns
                df_clean[f'{col}_category'] = categorization.apply(lambda x: x.get('category'))
                
                # Update residential and commercial units if they're found in the proposal
                # Only update if the value is greater than the existing value
                df_clean['residential_units'] = df_clean.apply(
                    lambda row: max(row.get('residential_units', 0), 
                                    categorization.loc[row.name].get('residential_units', 0)),
                    axis=1
                )
                df_clean['commercial_units'] = df_clean.apply(
                    lambda row: max(row.get('commercial_units', 0), 
                                    categorization.loc[row.name].get('commercial_units', 0)),
                    axis=1
                )
                
                # Update estimated_value based on residential units from categorization
                df_clean['estimated_value'] = df_clean.apply(
                    lambda row: categorization.loc[row.name].get('estimated_value') 
                              if pd.isna(row['estimated_value']) 
                              else row['estimated_value'],
                    axis=1
                )
                
                # Update householder_type column if it's a householder development
                df_clean['householder_type'] = df_clean.apply(
                    lambda row: categorization.loc[row.name].get('householder_type') 
                                if categorization.loc[row.name].get('is_householder', False) 
                                else row.get('householder_type'),
                    axis=1
                )
                
                # Extract other categorization details
                df_clean[f'{col}_is_householder'] = categorization.apply(lambda x: x.get('is_householder'))
                df_clean[f'{col}_is_conversion'] = categorization.apply(lambda x: x.get('is_conversion'))
                df_clean[f'{col}_conversion_type'] = categorization.apply(lambda x: x.get('conversion_type'))
                
                # Update stats for categories
                categories = df_clean[f'{col}_category'].value_counts().to_dict()
                for category, count in categories.items():
                    self.update_stats(f'proposal_category_{category}', count)
                
                # Log summary of categorization
                self.logger.info(f"Proposal categorization summary: {categories}")
        
        # Create a combined proposal_category column (using the first non-null category found)
        if any(f'{col}_category' in df_clean.columns for col in proposal_columns):
            category_columns = [f'{col}_category' for col in proposal_columns if f'{col}_category' in df_clean.columns]
            df_clean['proposal_category'] = df_clean[category_columns].bfill(axis=1).iloc[:, 0]
        
        # Copy site address to applicant address for householder developments and single unit residential
        # applications when applicant address is missing
        if all(col in df_clean.columns for col in ['applicant_address', 'site_address', 'proposal_category']):
            # Identify rows meeting the criteria:
            # 1. No applicant address
            # 2. Either householder development OR single unit residential
            missing_address_mask = pd.isna(df_clean['applicant_address']) | (df_clean['applicant_address'] == '')
            householder_mask = df_clean['proposal_category'] == 'householder_development'
            single_unit_mask = (df_clean['proposal_category'] == 'residential') & (df_clean['residential_units'] == 1)
            
            # Combined mask for rows that need address copying
            copy_address_mask = missing_address_mask & (householder_mask | single_unit_mask)
            
            # Copy site address to applicant address for qualifying rows
            df_clean.loc[copy_address_mask, 'applicant_address'] = df_clean.loc[copy_address_mask, 'site_address']
            
            # Also copy all the address components if they exist
            address_components = ['line1', 'line2', 'line3', 'town', 'area', 'county', 'city_district', 'postcode']
            for component in address_components:
                if f'site_address_{component}' in df_clean.columns and f'applicant_address_{component}' in df_clean.columns:
                    df_clean.loc[copy_address_mask, f'applicant_address_{component}'] = df_clean.loc[copy_address_mask, f'site_address_{component}']
            
            # Log the number of addresses copied
            addresses_copied = copy_address_mask.sum()
            if addresses_copied > 0:
                self.logger.info(f"Copied {addresses_copied} site addresses to applicant addresses for householder/single unit applications with missing applicant address")
        
        # Standardize date formats using our utility function
        date_columns = [
            'application_registered_date', 'decision_date', 'registration_date',
            'valid_from', 'dispatch_date', 'advert_expiry_date',
            'committee_date', 'consultation_expiry_date', 'consultation_start_date',
            'expiry_date', 'extended_target_decision_date', 'received_date',
            'site_visit_date', 'target_decision_date', 'planning_performance_agreement_due_date',
            'actual_committee_date', 'appeal_external_decision_date', 'final_grant_date',
            'extension_date', 'appeal_lodged_date', 'appeal_notify_date',
            'statutory_expiry_date', 'decision_expiry_date', 'publicity_end_date',
            'submission_expiry_date', 'application_date', 'decision_due_date',
            'press_notice_start_date', 'site_notice_date'
        ]
        
        for col in date_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(standardize_date)
        
        # Process phone number fields
        phone_columns = ['agent_phone', 'applicant_phone']
        for col in phone_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(standardize_phone_number)
        
        # Clean email addresses
        email_columns = ['agent_email', 'applicant_email']
        for col in email_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(clean_email_address)
        
        # Process numeric fields
        numeric_columns = ['residential_units', 'commercial_units', 'fee']
        for col in numeric_columns:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].apply(standardize_numeric)
        
        # Add metadata field to track transformation status
        df_clean['_transformed'] = True
        
        # Log final columns at the end of processing
        self.logger.info("==== COLUMNS AFTER PROCESSING ====")
        self.logger.info(f"DataFrame shape: {df_clean.shape}")
        for col in sorted(df_clean.columns):
            non_null = df_clean[col].count()
            total = len(df_clean)
            null_percentage = ((total - non_null) / total) * 100 if total > 0 else 0
            self.logger.info(f"  - {col}: {non_null}/{total} non-null values ({null_percentage:.1f}% empty)")
        self.logger.info("===================================")
        
        # Return a fresh copy to defragment the DataFrame (fixes performance warning)
        return df_clean.copy() 