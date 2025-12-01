#!/usr/bin/env python3
"""
Script to set up Companies House database table and load data from CSV file.
Only loads columns required by the lookup and integration scripts.
"""

import os
import csv
import logging
import argparse
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
from tqdm import tqdm

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create and return a database connection using environment variables."""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST'),
            dbname=os.getenv('POSTGRES_DB'),
            user=os.getenv('POSTGRES_USER'),
            password=os.getenv('POSTGRES_PASSWORD'),
            port=os.getenv('POSTGRES_PORT')
        )
        conn.set_session(autocommit=True)
        logger.info("Successfully connected to database")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

def create_companies_house_table(conn):
    """Create the companies_house table if it doesn't exist."""
    try:
        with conn.cursor() as cursor:
            # Check if table already exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'companies_house'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if table_exists:
                logger.info("companies_house table already exists")
                return
            
            # Create table
            cursor.execute("""
                CREATE TABLE companies_house (
                    id SERIAL PRIMARY KEY,
                    company_number TEXT UNIQUE NOT NULL,
                    company_name TEXT NOT NULL,
                    company_type TEXT,
                    address_line1 TEXT,
                    address_line2 TEXT,
                    city TEXT,
                    county TEXT,
                    country TEXT,
                    postcode TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX idx_companies_house_name ON companies_house (company_name);
                CREATE INDEX idx_companies_house_number ON companies_house (company_number);
            """)
            
            logger.info("Successfully created companies_house table and indexes")
    except Exception as e:
        logger.error(f"Error creating companies_house table: {e}")
        raise

def load_companies_house_data(conn, csv_path, batch_size=5000):
    """
    Load data from CSV file into companies_house table.
    Only loads required columns.
    """
    try:
        # First, check if file exists
        if not os.path.exists(csv_path):
            logger.error(f"CSV file not found: {csv_path}")
            return False

        # Check file size for progress bar
        file_size = os.path.getsize(csv_path)
        logger.info(f"Loading data from {csv_path} ({file_size/1024/1024:.2f} MB)")
        
        # CSV column mapping to database columns
        # These column names should match the CSV headers
        column_mapping = {
            'CompanyName': 'company_name',
            ' CompanyNumber': 'company_number',
            'RegAddress.AddressLine1': 'address_line1',
            ' RegAddress.AddressLine2': 'address_line2',
            'RegAddress.PostTown': 'city',
            'RegAddress.County': 'county',
            'RegAddress.Country': 'country',
            'RegAddress.PostCode': 'postcode',
            'CompanyCategory': 'company_type'
        }
        
        # Get the total number of rows for progress tracking
        with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
            total_rows = sum(1 for _ in f) - 1  # Subtract 1 for header
        
        with conn.cursor() as cursor:
            # Check if table already has data
            cursor.execute("SELECT COUNT(*) FROM companies_house")
            existing_count = cursor.fetchone()[0]
            
            if existing_count > 0:
                logger.warning(f"Table already contains {existing_count} rows. Consider truncating before loading.")
                response = input("Do you want to continue loading data? (y/n): ")
                if response.lower() != 'y':
                    logger.info("Data loading cancelled by user")
                    return False
            
            # Process the CSV file
            with open(csv_path, 'r', encoding='utf-8', errors='replace') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Extract CSV headers to verify our mapping
                csv_headers = reader.fieldnames
                logger.info(f"CSV headers: {csv_headers}")
                
                # Create a mapping from actual CSV headers to database columns
                actual_mapping = {}
                for header in csv_headers:
                    if header in column_mapping:
                        actual_mapping[header] = column_mapping[header]
                
                # Check if we found all required fields
                db_columns = ['company_number', 'company_name', 'company_type', 
                             'address_line1', 'city', 'postcode']
                missing_required = [col for col in db_columns if col not in actual_mapping.values()]
                
                if missing_required:
                    logger.error(f"Could not find mappings for required columns: {missing_required}")
                    logger.error(f"Available CSV headers: {csv_headers}")
                    logger.error(f"Current mapping: {column_mapping}")
                    return False
                
                logger.info(f"Using column mapping: {actual_mapping}")
                
                # Prepare the insert statement with the columns we found
                db_columns = list(set(actual_mapping.values()))  # Remove duplicates
                insert_query = sql.SQL("INSERT INTO companies_house ({}) VALUES ({}) ON CONFLICT (company_number) DO NOTHING").format(
                    sql.SQL(', ').join(map(sql.Identifier, db_columns)),
                    sql.SQL(', ').join(sql.Placeholder() * len(db_columns))
                )
                
                # Process in batches with progress bar
                batch = []
                processed = 0
                inserted = 0
                
                with tqdm(total=total_rows, desc="Loading data") as pbar:
                    for row in reader:
                        # Extract only the columns we need using our mapping
                        db_row = []
                        for csv_col, db_col in actual_mapping.items():
                            # Find position of this db_col in the db_columns list
                            if db_col in db_columns:
                                value = row.get(csv_col, '')
                                # Check for long values that might cause issues
                                if (db_col == 'company_number' or db_col == 'postcode') and len(value) > 20:
                                    logger.warning(f"Found {db_col} with length {len(value)}: '{value}'")
                                db_row.append(value)
                        
                        if len(db_row) == len(db_columns):  # Make sure we have all columns
                            batch.append(db_row)
                        
                        if len(batch) >= batch_size:
                            # Execute batch insert
                            cursor.executemany(insert_query, batch)
                            inserted += cursor.rowcount
                            batch = []
                            
                        processed += 1
                        pbar.update(1)
                        
                        # Periodically log progress
                        if processed % 100000 == 0:
                            logger.info(f"Processed {processed:,} rows, inserted {inserted:,} rows")
                
                # Insert any remaining records
                if batch:
                    cursor.executemany(insert_query, batch)
                    inserted += cursor.rowcount
                
                logger.info(f"Finished loading data. Processed {processed:,} rows, inserted {inserted:,} new records.")
                
                # Update statistics for PostgreSQL query planner
                logger.info("Analyzing table for query optimization...")
                cursor.execute("ANALYZE companies_house")
                
                return True
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Load Companies House data into database")
    parser.add_argument(
        "--csv", 
        default="/Users/andrewtaylor/Documents/GitHub/old-version/base/src/utils/BasicCompanyDataAsOneFile-2025-03-01.csv",
        help="Path to Companies House CSV file"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=5000,
        help="Batch size for database inserts"
    )
    parser.add_argument(
        "--recreate", 
        action="store_true",
        help="Drop and recreate the table before loading data"
    )
    args = parser.parse_args()
    
    try:
        conn = get_db_connection()
        
        # Drop table if recreate flag is set
        if args.recreate:
            with conn.cursor() as cursor:
                logger.info("Dropping companies_house table...")
                cursor.execute("DROP TABLE IF EXISTS companies_house CASCADE")
                logger.info("Table dropped successfully")
        
        # Create table if it doesn't exist
        create_companies_house_table(conn)
        
        # Load data
        success = load_companies_house_data(conn, args.csv, args.batch_size)
        
        if success:
            logger.info("Companies House data loaded successfully")
        else:
            logger.error("Failed to load Companies House data")
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    main() 