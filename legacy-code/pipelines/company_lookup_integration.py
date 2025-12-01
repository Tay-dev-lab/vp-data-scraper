import logging
from .companies_house_lookup import PostgresCompanyLookup
from dotenv import load_dotenv

# Ensure env vars are loaded here as well
load_dotenv()

logger = logging.getLogger(__name__)

class CompanyLookupIntegration:
    """
    Integrates company lookup functionality with the data transformation pipeline.
    This class handles looking up company names in the Companies House database.
    """
    
    def __init__(self, db_params=None):
        """
        Initialize with database connection parameters.
        
        Args:
            db_params: Dictionary of PostgreSQL connection parameters (optional)
                       If None, will use environment variables
        """
        logger.info("Initializing CompanyLookupIntegration")
        if db_params:
            logger.info("Using provided database parameters")
        else:
            logger.info("No DB params provided, will use environment variables")
            
        self.company_lookup = PostgresCompanyLookup(db_params)
        
        # Log connection status
        if hasattr(self.company_lookup, 'conn') and self.company_lookup.conn:
            logger.info("Successfully connected to Companies House database")
        else:
            logger.warning("Could not connect to Companies House database")
            
        self.stats = {
            'total_lookups': 0,
            'agent_companies_matched': 0,
            'applicant_companies_matched': 0
        }
    
    def process_dataframe(self, df):
        """
        Process a dataframe by looking up company names in the Companies House database.
        
        Args:
            df: Pandas DataFrame containing agent_company_name and/or applicant_company_name columns
            
        Returns:
            Processed DataFrame with company details added
        """
        logger.info("Starting company lookup processing")
        
        # Process agent company names if the column exists
        if 'agent_company_name' in df.columns:
            logger.info(f"Processing {df['agent_company_name'].notna().sum()} agent company names")
            
            # Only process rows with non-null agent_company_name values
            mask = df['agent_company_name'].notna()
            
            if mask.any():
                # Log sample of company names we're looking up
                sample_names = df.loc[mask, 'agent_company_name'].head(5).tolist()
                logger.info(f"Sample agent company names: {sample_names}")
                
                # Apply the company lookup function to each value
                results = df.loc[mask, 'agent_company_name'].apply(self.company_lookup.find_company)
                
                # Count successful matches
                matches = sum(1 for r in results if r['match_type'] == 'exact')
                self.stats['agent_companies_matched'] += matches
                self.stats['total_lookups'] += len(results)
                
                logger.info(f"Found {matches} exact matches for agent companies")
                
                # Add the results to the dataframe using correct field names
                df.loc[mask, 'agent_company_reg_name'] = results.apply(lambda x: x.get('company_name'))
                df.loc[mask, 'agent_company_reg_number'] = results.apply(lambda x: x.get('company_number'))
                df.loc[mask, 'agent_company_reg_registered_address'] = results.apply(lambda x: x.get('registered_address'))
                df.loc[mask, 'agent_company_reg_address_line1'] = results.apply(lambda x: x.get('address_line1'))
                df.loc[mask, 'agent_company_reg_address_line2'] = results.apply(lambda x: x.get('address_line2'))
                df.loc[mask, 'agent_company_reg_city'] = results.apply(lambda x: x.get('city'))
                df.loc[mask, 'agent_company_reg_county'] = results.apply(lambda x: x.get('county'))
                df.loc[mask, 'agent_company_reg_country'] = results.apply(lambda x: x.get('country'))
                df.loc[mask, 'agent_company_reg_postcode'] = results.apply(lambda x: x.get('postcode'))
                df.loc[mask, 'agent_company_reg_type'] = results.apply(lambda x: x.get('company_type'))
                
                # Check if we actually added any data
                non_null_companies = df.loc[mask, 'agent_company_reg_number'].notna().sum()
                logger.info(f"Added company registration data for {non_null_companies} agent companies")
                
                # If we have no matches, log a warning
                if non_null_companies == 0 and matches > 0:
                    logger.warning("Matches found but no agent company data was added to the dataframe. Check field mapping.")
            else:
                logger.info("No agent company names to process")
        
        # Process applicant company names if the column exists
        if 'applicant_company_name' in df.columns:
            logger.info(f"Processing {df['applicant_company_name'].notna().sum()} applicant company names")
            
            # Only process rows with non-null applicant_company_name values
            mask = df['applicant_company_name'].notna()
            
            if mask.any():
                # Log sample of company names we're looking up
                sample_names = df.loc[mask, 'applicant_company_name'].head(5).tolist()
                logger.info(f"Sample applicant company names: {sample_names}")
                
                # Apply the company lookup function to each value
                results = df.loc[mask, 'applicant_company_name'].apply(self.company_lookup.find_company)
                
                # Count successful matches
                matches = sum(1 for r in results if r['match_type'] == 'exact')
                self.stats['applicant_companies_matched'] += matches
                self.stats['total_lookups'] += len(results)
                
                logger.info(f"Found {matches} exact matches for applicant companies")
                
                # Add the results to the dataframe using correct field names
                df.loc[mask, 'applicant_company_reg_name'] = results.apply(lambda x: x.get('company_name'))
                df.loc[mask, 'applicant_company_reg_number'] = results.apply(lambda x: x.get('company_number'))
                df.loc[mask, 'applicant_company_reg_registered_address'] = results.apply(lambda x: x.get('registered_address'))
                df.loc[mask, 'applicant_company_reg_address_line1'] = results.apply(lambda x: x.get('address_line1'))
                df.loc[mask, 'applicant_company_reg_address_line2'] = results.apply(lambda x: x.get('address_line2'))
                df.loc[mask, 'applicant_company_reg_city'] = results.apply(lambda x: x.get('city'))
                df.loc[mask, 'applicant_company_reg_county'] = results.apply(lambda x: x.get('county'))
                df.loc[mask, 'applicant_company_reg_country'] = results.apply(lambda x: x.get('country'))
                df.loc[mask, 'applicant_company_reg_postcode'] = results.apply(lambda x: x.get('postcode'))
                df.loc[mask, 'applicant_company_reg_type'] = results.apply(lambda x: x.get('company_type'))
                
                # Check if we actually added any data
                non_null_companies = df.loc[mask, 'applicant_company_reg_number'].notna().sum()
                logger.info(f"Added company registration data for {non_null_companies} applicant companies")
                
                # If we have no matches, log a warning
                if non_null_companies == 0 and matches > 0:
                    logger.warning("Matches found but no applicant company data was added to the dataframe. Check field mapping.")
            else:
                logger.info("No applicant company names to process")
        
        logger.info(f"Company lookup processing complete. Stats: {self.stats}")
        
        return df 