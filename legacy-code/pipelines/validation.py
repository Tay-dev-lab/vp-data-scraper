from typing import Dict, List, Any, Tuple, Optional, Union, Set
from pydantic import BaseModel, field_validator, model_validator, EmailStr, ValidationError, Field
from datetime import datetime
import json
import uuid
import csv
from pathlib import Path
from .base import BasePipeline
from itemadapter import ItemAdapter

# -------- Pydantic Model for Validation -------- #

class PlanningAppValidation(BaseModel):
    """
    Comprehensive validation model for planning application data.
    Only site_address and proposal are required.
    All other fields are optional with loose validation.
    """
    # Unique reference ID - will be automatically generated
    reference_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    
    # All fields from transformed_data_20250324_133418.csv
    # Required fields
    site_address: str
    proposal: str
    
    # All other fields (optional)
    council_name: Optional[str] = None
    application_reference: Optional[str] = None
    status: Optional[str] = None
    valid_from: Optional[str] = None
    application_url: Optional[str] = None
    registration_date: Optional[str] = None
    decision: Optional[str] = None
    decision_date: Optional[str] = None
    application_type: Optional[str] = None
    determination_level: Optional[str] = None
    case_officer_name: Optional[str] = None
    parish: Optional[str] = None
    ward: Optional[str] = None
    applicant_name: Optional[str] = None
    applicant_address: Optional[str] = None
    environmental_assessment_required: Optional[str] = None
    expiry_date: Optional[str] = None
    consultation_start_date: Optional[str] = None
    consultation_expiry_date: Optional[str] = None
    target_decision_date: Optional[str] = None
    statutory_expiry_date: Optional[str] = None
    dispatch_date: Optional[str] = None
    decision_due_date: Optional[str] = None
    agent_name: Optional[str] = None
    agent_address: Optional[str] = None
    agent_company_name: Optional[str] = None
    agent_phone: Optional[str] = None
    site_notice_date: Optional[str] = None
    publicity_end_date: Optional[str] = None
    decision_expiry_date: Optional[str] = None
    agent_name_first: Optional[str] = None
    agent_name_middle: Optional[str] = None
    agent_name_last: Optional[str] = None
    agent_name_title: Optional[str] = None
    agent_name_suffix: Optional[str] = None
    agent_name_gender: Optional[str] = None
    agent_name_salutation: Optional[str] = None
    applicant_company_name: Optional[str] = None
    applicant_name_first: Optional[str] = None
    applicant_name_middle: Optional[str] = None
    applicant_name_last: Optional[str] = None
    applicant_name_title: Optional[str] = None
    applicant_name_suffix: Optional[str] = None
    applicant_name_gender: Optional[str] = None
    applicant_name_salutation: Optional[str] = None
    agent_company_reg_name: Optional[str] = None
    agent_company_reg_number: Optional[str] = None
    agent_company_reg_registered_address: Optional[str] = None
    agent_company_reg_address_line1: Optional[str] = None
    agent_company_reg_address_line2: Optional[str] = None
    agent_company_reg_city: Optional[str] = None
    agent_company_reg_county: Optional[str] = None
    agent_company_reg_country: Optional[str] = None
    agent_company_reg_postcode: Optional[str] = None
    agent_company_reg_type: Optional[str] = None
    applicant_company_reg_name: Optional[str] = None
    applicant_company_reg_number: Optional[str] = None
    applicant_company_reg_registered_address: Optional[str] = None
    applicant_company_reg_address_line1: Optional[str] = None
    applicant_company_reg_address_line2: Optional[str] = None
    applicant_company_reg_city: Optional[str] = None
    applicant_company_reg_county: Optional[str] = None
    applicant_company_reg_country: Optional[str] = None
    applicant_company_reg_postcode: Optional[str] = None
    applicant_company_reg_type: Optional[str] = None
    applicant_address_line1: Optional[str] = None
    applicant_address_line2: Optional[str] = None
    applicant_address_town: Optional[str] = None
    applicant_address_city: Optional[str] = None
    applicant_address_county: Optional[str] = None
    applicant_address_country: Optional[str] = None
    applicant_address_postcode: Optional[str] = None
    agent_address_line1: Optional[str] = None
    agent_address_line2: Optional[str] = None
    agent_address_town: Optional[str] = None
    agent_address_city: Optional[str] = None
    agent_address_county: Optional[str] = None
    agent_address_country: Optional[str] = None
    agent_address_postcode: Optional[str] = None
    site_address_line1: Optional[str] = None
    site_address_line2: Optional[str] = None
    site_address_town: Optional[str] = None
    site_address_city: Optional[str] = None
    site_address_county: Optional[str] = None
    site_address_country: Optional[str] = None
    site_address_postcode: Optional[str] = None
    residential_units: Optional[float] = None
    commercial_units: Optional[float] = None
    estimated_value: Optional[str] = None
    householder_type: Optional[str] = None
    proposal_category: Optional[str] = None
    proposal_is_householder: Optional[bool] = None
    proposal_is_conversion: Optional[bool] = None
    proposal_conversion_type: Optional[str] = None
    _transformed: Optional[bool] = None
    
    # Additional field to store validation status
    _validation_status: Optional[str] = None
    
    # Validators - updated to Pydantic v2 syntax
    @field_validator('site_address', 'proposal')
    @classmethod
    def required_fields_not_empty(cls, v, info):
        if not v or not v.strip():
            raise ValueError(f'{info.field_name} cannot be empty')
        return v
    
    # Validator for company registration fields (handles NULL/NaN values)
    @field_validator('agent_company_reg_name', 'agent_company_reg_number', 
                  'agent_company_reg_registered_address', 'agent_company_reg_address_line1',
                  'agent_company_reg_address_line2', 'agent_company_reg_city', 
                  'agent_company_reg_county', 'agent_company_reg_country',
                  'agent_company_reg_postcode', 'agent_company_reg_type',
                  'applicant_company_reg_name', 'applicant_company_reg_number', 
                  'applicant_company_reg_registered_address', 'applicant_company_reg_address_line1',
                  'applicant_company_reg_address_line2', 'applicant_company_reg_city', 
                  'applicant_company_reg_county', 'applicant_company_reg_country',
                  'applicant_company_reg_postcode', 'applicant_company_reg_type')
    @classmethod
    def sanitize_company_fields(cls, v):
        # Return None for any non-string values or empty strings
        if not isinstance(v, str) or not v.strip():
            return None
        return v
    
    @field_validator('valid_from', 'registration_date', 'decision_date', 'expiry_date', 
               'consultation_start_date', 'consultation_expiry_date', 'target_decision_date',
               'statutory_expiry_date', 'dispatch_date', 'decision_due_date',
               'site_notice_date', 'publicity_end_date', 'decision_expiry_date')
    @classmethod
    def validate_date_format(cls, v):
        if v:
            # Normalize date to YYYY-MM-DD format
            try:
                # Check if it's already in YYYY-MM-DD format
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                try:
                    # Try DD/MM/YYYY format
                    parsed_date = datetime.strptime(v, '%d/%m/%Y')
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    try:
                        # Try other common formats
                        parsed_date = datetime.strptime(v, '%Y/%m/%d')
                        return parsed_date.strftime('%Y-%m-%d')
                    except ValueError:
                        try:
                            parsed_date = datetime.strptime(v, '%d-%m-%Y')
                            return parsed_date.strftime('%Y-%m-%d')
                        except ValueError:
                            try:
                                parsed_date = datetime.strptime(v, '%m/%d/%Y')
                                return parsed_date.strftime('%Y-%m-%d')
                            except ValueError:
                                # Add support for day of week format (e.g., "Thu 06 Feb 2025")
                                try:
                                    parsed_date = datetime.strptime(v, '%a %d %b %Y')
                                    return parsed_date.strftime('%Y-%m-%d')
                                except ValueError:
                                    # If all parsing attempts fail, raise validation error
                                    raise ValueError(f'Invalid date format: {v}. Expected YYYY-MM-DD, DD/MM/YYYY, or similar format')
        return v
    
    @field_validator('agent_phone')
    @classmethod
    def validate_phone(cls, v):
        if v:
            # More robust phone validation
            # Remove all characters except digits, +, -, (, ), and spaces
            cleaned = ''.join(c for c in v if c.isdigit() or c in '+-() ')
            
            # Ensure there are at least 6 digits in the phone number
            if len([c for c in cleaned if c.isdigit()]) < 6:
                raise ValueError(f'Phone number must contain at least 6 digits: {v}')
            
            return cleaned
        return v
    
    @model_validator(mode='after')
    def ensure_addresses_consistent(self) -> 'PlanningAppValidation':
        # This validator ensures that if site_address components are provided,
        # they are consistent with the main site_address field
        site_address = self.site_address
        site_components = [
            self.site_address_line1,
            self.site_address_line2,
            self.site_address_town,
            self.site_address_city,
            self.site_address_county,
            self.site_address_postcode
        ]
        
        # If site_address is not provided but components are, construct site_address
        if not site_address and any(site_components):
            self.site_address = ', '.join([c for c in site_components if c])
        
        return self


class ValidationPipeline(BasePipeline):
    """
    Pipeline stage: Data validation using a comprehensive Pydantic model
    
    Responsibilities:
    - Validate data using the PlanningAppValidation model
    - Handle validation errors and store rejected items with detailed logging
    - Output all results (validated and rejected) to CSV
    """
    
    def __init__(self, settings=None):
        super().__init__(settings)
        self.rejected_items_path = settings.get('REJECTED_ITEMS_PATH', 'rejected_items.jsonl') if settings else 'rejected_items.jsonl'
        self.output_csv_path = settings.get('VALIDATION_OUTPUT_PATH', 'validation_output.csv') if settings else 'validation_output.csv'
        self.validated_items = []
        self.rejected_items = []
        # Track processed application references to avoid duplicates
        self.processed_refs = set()
        
    def process_item(self, item, spider):
        # Use ItemAdapter to handle different item types consistently
        adapter = ItemAdapter(item)
        
        # Log information about the incoming item
        if '_batch_items' in adapter:
            batch_size = len(adapter.get('_batch_items', []))
            self.logger.info(f"Received batch of {batch_size} transformed items from transformation pipeline")
        else:
            app_ref = adapter.get('application_reference', 'unknown')
            self.logger.info(f"Received single item {app_ref} from transformation pipeline")
        
        # Extract batch items from metadata if present
        batch_items = []
        if '_batch_items' in adapter:
            # Get the batch items
            batch_items = adapter.get('_batch_items', [])
            # If it's not a Scrapy Item, we can modify it directly
            if hasattr(item, 'pop'):
                item.pop('_batch_items', None)
        else:
            # If no batch items found, just process this item alone
            batch_items = [item]
        
        # Filter out any already processed items by application reference
        # This prevents duplicate validation
        unique_batch_items = []
        for batch_item in batch_items:
            # Use ItemAdapter for consistent access
            batch_adapter = ItemAdapter(batch_item)
            app_ref = batch_adapter.get('application_reference')
            
            # Skip items we've already processed, unless they don't have an application reference
            if app_ref and app_ref in self.processed_refs:
                self.logger.info(f"Skipping duplicate item with reference: {app_ref}")
                continue
                
            # Track this reference as processed
            if app_ref:
                self.processed_refs.add(app_ref)
                self.logger.debug(f"Tracking application reference {app_ref} as processed")
                
            unique_batch_items.append(batch_item)
            
        # Only process unique items
        if not unique_batch_items:
            self.logger.info("All items in batch were duplicates, skipping validation")
            return None
            
        # Validate unique batch items
        valid_items, rejected_items = self._validate_items(unique_batch_items)
        
        # Store all items for later CSV output
        self.validated_items.extend(valid_items)
        self.rejected_items.extend(rejected_items)
        self.logger.info(f"Added batch items to ongoing totals. Total valid items so far: {len(self.validated_items)}")
        
        # Write intermediate results to CSV after each batch
        self._output_results_to_csv(intermediate=True)
        
        # Update stats
        self.update_stats('items_validated', len(unique_batch_items))
        self.update_stats('items_valid', len(valid_items))
        self.update_stats('items_rejected', len(rejected_items))
        
        # Pass first valid item to next pipeline with metadata for the rest
        if valid_items:
            # Always return as dictionary to avoid KeyErrors
            first_item = dict(valid_items[0])
            first_item['_valid_batch'] = valid_items
            self.logger.info(f"Validation complete: {len(valid_items)} valid items, {len(rejected_items)} rejected items")
            return first_item
        
        # If no valid items, drop this batch
        self.logger.info("No valid items found in batch, dropping batch")
        return None
    
    def close_spider(self, spider):
        # Save rejected items to file with detailed logs
        if self.rejected_items:
            self._save_rejected_items()
        
        # Output final results to CSV
        self._output_results_to_csv(intermediate=False)
        
        super().close_spider(spider)
    
    def _validate_items(self, items):
        """Validate items using the PlanningAppValidation model"""
        valid_items = []
        rejected_items = []
        
        for item in items:
            # Convert to dictionary with ItemAdapter if it's a Scrapy Item
            item_dict = dict(ItemAdapter(item))
            
            # Pre-process company registration fields to handle NULL values
            company_fields = [
                'agent_company_reg_name', 'agent_company_reg_number', 
                'agent_company_reg_registered_address', 'agent_company_reg_address_line1',
                'agent_company_reg_address_line2', 'agent_company_reg_city', 
                'agent_company_reg_county', 'agent_company_reg_country',
                'agent_company_reg_postcode', 'agent_company_reg_type',
                'applicant_company_reg_name', 'applicant_company_reg_number', 
                'applicant_company_reg_registered_address', 'applicant_company_reg_address_line1',
                'applicant_company_reg_address_line2', 'applicant_company_reg_city', 
                'applicant_company_reg_county', 'applicant_company_reg_country',
                'applicant_company_reg_postcode', 'applicant_company_reg_type'
            ]
            
            # Set any non-string values to None
            for field in company_fields:
                if field in item_dict and not isinstance(item_dict[field], str):
                    item_dict[field] = None
            
            try:
                # Try to validate the entire item using Pydantic v2 syntax
                validated_item = PlanningAppValidation.model_validate(item_dict).model_dump()
                
                # Add validation status metadata to the dictionary
                validated_item['_validated'] = True
                validated_item['_validation_status'] = 'success'
                valid_items.append(validated_item)
                
            except ValidationError as e:
                # Detailed error logging for rejected items
                errors = {}
                for error in e.errors():
                    field = '.'.join(str(loc) for loc in error['loc'])
                    message = error['msg']
                    errors[field] = message
                
                # Create new dictionary for rejected item instead of modifying original
                invalid_item = item_dict.copy()
                invalid_item['_validated'] = False
                invalid_item['_validation_status'] = 'rejected'
                invalid_item['_validation_errors'] = errors
                # Still assign a reference ID even to rejected items for tracking
                invalid_item['reference_id'] = str(uuid.uuid4())
                
                rejected_items.append(invalid_item)
                self.logger.warning(f"Validation failed for {invalid_item.get('application_reference', 'unknown reference')}: {', '.join([f'{k}: {v}' for k, v in errors.items()])}")
                
        return valid_items, rejected_items
    
    def _save_rejected_items(self):
        """Save rejected items to a JSONL file with detailed error information"""
        path = Path(self.rejected_items_path)
        
        # Create directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as f:
            for item in self.rejected_items:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                
        self.logger.info(f"Saved {len(self.rejected_items)} rejected items to {self.rejected_items_path}")
        
        # Log detailed error information for each rejected item
        for i, item in enumerate(self.rejected_items):
            errors = item.get('_validation_errors', {})
            app_ref = item.get('application_reference', f'Item #{i+1}')
            self.logger.info(f"Rejected item {app_ref}:")
            for field, message in errors.items():
                self.logger.info(f"  - {field}: {message}")
    
    def _output_results_to_csv(self, intermediate=False):
        """Output all validation results to CSV file (validation_output.csv)"""
        # Combine all items
        all_items = self.validated_items + self.rejected_items
        if not all_items:
            self.logger.info("No items to output to CSV")
            return
        
        # Get all possible fields from the items
        all_fields: Set[str] = set()
        for item in all_items:
            all_fields.update(item.keys())
        
        # Ensure important fields come first in the CSV
        priority_fields = [
            'reference_id', '_validation_status', 'council_name', 'application_reference',
            'site_address', 'proposal', 'status', 'decision', '_validation_errors'
        ]
        
        # Order fields with priority fields first, followed by others in alphabetical order
        ordered_fields = [f for f in priority_fields if f in all_fields]
        ordered_fields.extend(sorted([f for f in all_fields if f not in priority_fields]))
        
        # Write to CSV
        path = Path(self.output_csv_path)
        if intermediate:
            # For intermediate outputs, use a different filename to avoid concurrent writes
            path = Path(f"{self.output_csv_path.rstrip('.csv')}_running.csv")
        
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=ordered_fields, extrasaction='ignore')
            writer.writeheader()
            
            # Write all items
            for item in all_items:
                # Convert complex fields to strings for CSV
                row = {}
                for k, v in item.items():
                    if isinstance(v, dict) or isinstance(v, list):
                        row[k] = json.dumps(v)
                    else:
                        row[k] = v
                writer.writerow(row)
        
        log_message = f"Output {len(all_items)} items to {path} " + \
                      f"({len(self.validated_items)} valid, {len(self.rejected_items)} rejected)"
        if intermediate:
            self.logger.debug(log_message + " (intermediate output)")
        else:
            self.logger.info(log_message)