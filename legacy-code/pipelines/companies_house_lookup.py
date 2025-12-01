import psycopg2
import psycopg2.extras
import re
import logging
import os
from functools import lru_cache
from typing import Dict, Optional
from dotenv import load_dotenv
import socket

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class PostgresCompanyLookup:
    def __init__(self, db_params=None):
        """
        Initialize with database connection parameters.
        
        Args:
            db_params: Dictionary of PostgreSQL connection parameters
        """
        # Use provided db_params if any, otherwise use environment variables
        if not db_params:
            self.db_params = {
                'host': os.getenv('POSTGRES_HOST'),
                'dbname': os.getenv('POSTGRES_DB'),
                'user': os.getenv('POSTGRES_USER'),
                'password': os.getenv('POSTGRES_PASSWORD'),
                'port': os.getenv('POSTGRES_PORT')
            }
            logger.info(f"Using database connection from environment variables: host={self.db_params['host']}, db={self.db_params['dbname']}")
        else:
            self.db_params = db_params
            logger.info(f"Using provided database parameters: host={self.db_params.get('host')}, db={self.db_params.get('dbname')}")
        
        # Validate required parameters
        missing_params = [k for k, v in self.db_params.items() if not v and k != 'port']
        if missing_params:
            logger.error(f"Missing required database parameters: {missing_params}")
            self.conn = None
            return
            
        # Add connection timeout
        self.db_params['connect_timeout'] = 10
        
        try:
            # Test if host is reachable first
            host = self.db_params['host']
            port = int(self.db_params.get('port', 5432))
            
            logger.info(f"Testing connection to {host}:{port}")
            socket_test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            socket_test.settimeout(5)
            
            result = socket_test.connect_ex((host, port))
            socket_test.close()
            
            if result != 0:
                logger.error(f"Cannot reach database host {host}:{port} - connection failed")
                self.conn = None
                return
                
            logger.info(f"Host {host}:{port} is reachable, attempting database connection")
            self.conn = psycopg2.connect(**self.db_params)
            logger.info("Successfully connected to database")
            
            # Enable connection pooling for better performance
            self.conn.set_session(autocommit=True)
            
            # Check if companies_house table exists and has data
            with self.conn.cursor() as cursor:
                try:
                    cursor.execute("SELECT COUNT(*) FROM companies_house")
                    count = cursor.fetchone()[0]
                    logger.info(f"Found {count} records in companies_house table")
                    
                    if count == 0:
                        logger.warning("companies_house table exists but contains no records")
                    
                except Exception as e:
                    logger.error(f"Error checking companies_house table: {e}")
                    # Table might not exist
                    self.conn = None
                    
        except psycopg2.OperationalError as e:
            logger.error(f"Failed to connect to database: {e}")
            self.conn = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to database: {e}")
            self.conn = None
        
        # Initialize LRU cache for recent lookups
        self.cache = {}
        self.cache_max_size = 1000
        self.cache_stats = {'hits': 0, 'misses': 0}
    
    def __del__(self):
        """Close connection on object deletion."""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
    
    def clean_text(self, text: str) -> str:
        """
        Standardize text for better matching by normalizing company names.
        
        This function:
        1. Converts to lowercase
        2. Normalizes common company suffixes (ltd/limited)
        3. Removes special characters and extra whitespace
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace ampersands for consistency
        text = text.replace('&', 'and')
        
        # Normalize common company suffixes
        text = re.sub(r'\bltd\.?$|\blimited$|\bltd$', 'limited', text)
        text = re.sub(r'\binc\.?$|\bincorporated$', 'incorporated', text)
        text = re.sub(r'\bco\.?$|\bcompany$', 'company', text)
        text = re.sub(r'\bplc$|\bp\.?l\.?c\.?$', 'plc', text)
        text = re.sub(r'\bllp$|\bl\.?l\.?p\.?$', 'llp', text)
        
        # Remove punctuation except spaces
        text = re.sub(r'[^\w\s]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    # Use LRU cache to avoid repeated lookups of the same company name
    @lru_cache(maxsize=500)
    def exact_match(self, company_name: str) -> Optional[Dict]:
        """Find exact match for company name."""
        if not company_name:
            logger.debug(f"Skipping lookup for empty company name")
            return None
        
        if not self.conn:
            logger.error("Database connection not available")
            return None
        
        clean_name = self.clean_text(company_name)
        logger.debug(f"Looking up '{company_name}' (cleaned to '{clean_name}')")
        
        try:
            with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Try exact match first
                cursor.execute(
                    "SELECT * FROM companies_house WHERE LOWER(company_name) = %s",
                    (clean_name,)
                )
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"Found exact match for '{company_name}': {result['company_name']} (company number: {result['company_number']})")
                    return dict(result)
                
                # If no exact match, try with simplified company suffixes
                cursor.execute(
                    """
                    SELECT * FROM companies_house 
                    WHERE LOWER(company_name) LIKE %s
                    OR LOWER(company_name) LIKE %s
                    """,
                    (f"{clean_name} %", f"{clean_name}")
                )
                result = cursor.fetchone()
                
                if result:
                    logger.info(f"Found suffix match for '{company_name}': {result['company_name']} (company number: {result['company_number']})")
                    return dict(result)
                
                logger.debug(f"No match found for company: '{company_name}'")
                return None
        except Exception as e:
            logger.error(f"Database error looking up '{company_name}': {e}")
            return None
    
    def find_company(self, company_name: str) -> Dict:
        """Main method to find a company by name using exact matching."""
        if not company_name:
            logger.debug("find_company called with empty company name")
            return {
                'company_name': None,
                'company_number': None,
                'registered_address': None,
                'match_type': 'none',
                'confidence': 0,
                'original_text': company_name
            }
        
        logger.debug(f"Processing company: '{company_name}'")
        
        # Clean input text
        clean_name = self.clean_text(company_name)
        
        # Skip extremely short names to avoid false positives
        if len(clean_name) < 3:
            logger.debug(f"Skipping '{company_name}': too short after cleaning ('{clean_name}')")
            return {
                'company_name': None,
                'company_number': None,
                'registered_address': None,
                'match_type': 'none',
                'confidence': 0,
                'original_text': company_name
            }
        
        # Try exact match
        match = self.exact_match(clean_name)
        if match:
            result = {
                'company_name': match['company_name'],
                'company_number': match['company_number'],
                'registered_address': f"{match['address_line1']}, {match['city']}, {match['postcode']}",
                'address_line1': match['address_line1'],
                'city': match['city'],
                'postcode': match['postcode'],
                'match_type': 'exact',
                'confidence': 1.0,
                'original_text': company_name
            }
            logger.debug(f"Returning match for '{company_name}': {result}")
            return result
        
        # No matching company found in database
        logger.debug(f"No match found for '{company_name}'")
        return {
            'company_name': company_name,  # Return original name as provided
            'company_number': None,
            'registered_address': None,
            'match_type': 'none',
            'confidence': 0,
            'original_text': company_name
        }