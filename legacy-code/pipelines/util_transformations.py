"""
Utility functions for data transformations.

This module contains reusable transformation functions for dates, phone numbers,
emails, and other common data types that need standardization.
"""

from datetime import datetime
import re
import logging
import pandas as pd
from typing import Optional, Union, Any

logger = logging.getLogger(__name__)

def standardize_date(date_input: Any) -> Optional[str]:
    """
    Convert various date and datetime formats to YYYY-MM-DD.
    
    Args:
        date_input: Date string, datetime object, or other input to standardize
        
    Returns:
        Standardized date string in YYYY-MM-DD format or None if parsing fails
    """
    # Handle None, NaN, empty strings
    if date_input is None or pd.isna(date_input) or (isinstance(date_input, str) and not date_input.strip()):
        return None
    
    # If already a datetime object, just format it
    if isinstance(date_input, datetime):
        return date_input.strftime('%Y-%m-%d')
    
    # If not a string, try to convert to string first
    if not isinstance(date_input, str):
        try:
            date_input = str(date_input)
        except:
            return None
    
    # Clean and prepare the string
    date_str = date_input.strip()
    
    # Handle common date formats
    date_formats = [
        '%Y-%m-%d',          # 2023-01-30
        '%d/%m/%Y',          # 30/01/2023
        '%d-%m-%Y',          # 30-01-2023
        '%m/%d/%Y',          # 01/30/2023
        '%d.%m.%Y',          # 30.01.2023
        '%B %d, %Y',         # January 30, 2023
        '%d %B %Y',          # 30 January 2023
        '%Y/%m/%d',          # 2023/01/30
        '%a %d %b %Y',       # Tue 25 Feb 2025
        '%A %d %B %Y',       # Tuesday 25 February 2025
    ]
    
    # Handle datetime formats (with time components)
    datetime_formats = [
        '%Y-%m-%d %H:%M:%S',  # 2023-01-30 14:30:45
        '%d/%m/%Y %H:%M:%S',  # 30/01/2023 14:30:45
        '%Y-%m-%dT%H:%M:%S',  # 2023-01-30T14:30:45
        '%Y-%m-%dT%H:%M:%SZ', # 2023-01-30T14:30:45Z (ISO format)
        '%Y-%m-%d %H:%M',     # 2023-01-30 14:30
        '%d/%m/%Y %H:%M',     # 30/01/2023 14:30
    ]
    
    # Try parsing with date formats first
    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If that fails, try datetime formats
    for fmt in datetime_formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # One last attempt: try to find a date pattern in the string
    # This can handle strings like "Created on 2023-01-30" or "Date: 30/01/2023"
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',                # YYYY-MM-DD
        r'(\d{2}/\d{2}/\d{4})',                # DD/MM/YYYY or MM/DD/YYYY
        r'(\d{2}-\d{2}-\d{4})',                # DD-MM-YYYY or MM-DD-YYYY
        r'(\d{2}\.\d{2}\.\d{4})',              # DD.MM.YYYY
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, date_str)
        if match:
            extracted_date = match.group(1)
            # Try parsing the extracted date with our formats
            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(extracted_date, fmt)
                    return date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    continue
    
    # If we still couldn't parse it, log a warning and return the original
    logger.warning(f"Could not standardize date: {date_str}")
    return date_str

def standardize_phone_number(phone_input: Any) -> Optional[str]:
    """
    Standardize phone numbers by removing non-numeric characters and formatting consistently.
    
    Args:
        phone_input: Phone number string or other input to standardize
        
    Returns:
        Formatted phone number or None if input is invalid
    """
    # Handle None, NaN, empty strings
    if phone_input is None or pd.isna(phone_input) or (isinstance(phone_input, str) and not phone_input.strip()):
        return None
    
    # Convert to string if not already
    if not isinstance(phone_input, str):
        try:
            phone_input = str(phone_input)
        except:
            return None
    
    # Extract only digits
    digits = re.sub(r'\D', '', phone_input)
    
    # Check if we have a valid number of digits
    if len(digits) < 7:  # Most phone numbers have at least 7 digits
        return None
    
    # UK numbers often start with 0 and have 10-11 digits
    if digits.startswith('44') and len(digits) >= 10:
        # Convert international format +44 to UK format 0
        digits = '0' + digits[2:]
    
    # Format UK numbers: 07XXX XXXXXX (mobile), 01XXX XXXXXX or 02X XXXX XXXX (landline)
    if len(digits) == 11:
        if digits.startswith('07'):  # Mobile
            return f"{digits[0:5]} {digits[5:]}"
        elif digits.startswith('01') or digits.startswith('02'):  # Landline
            return f"{digits[0:5]} {digits[5:]}"
        else:
            return f"{digits}"
    elif len(digits) == 10:
        return f"{digits[0:4]} {digits[4:]}" 
    
    # If we can't determine the format, just return the digits
    return digits

def clean_email_address(email_input: Any) -> Optional[str]:
    """
    Clean and validate email addresses, fixing common issues.
    
    Args:
        email_input: Email string or other input to clean
        
    Returns:
        Cleaned email address or None if input is invalid
    """
    # Handle None, NaN, empty strings
    if email_input is None or pd.isna(email_input) or (isinstance(email_input, str) and not email_input.strip()):
        return None
    
    # Convert to string if not already
    if not isinstance(email_input, str):
        try:
            email_input = str(email_input)
        except:
            return None
    
    # Strip whitespace and convert to lowercase
    email = email_input.strip().lower()
    
    # Basic pattern match to validate email format
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        # Try to fix common issues
        
        # Remove extra spaces
        email = re.sub(r'\s', '', email)
        
        # Check for missing @ symbol
        if '@' not in email:
            logger.warning(f"Invalid email (missing @ symbol): {email_input}")
            return None
        
        # Check for multiple @ symbols
        if email.count('@') > 1:
            logger.warning(f"Invalid email (multiple @ symbols): {email_input}")
            return None
        
        # Validate corrected email
        if not re.match(email_pattern, email):
            logger.warning(f"Invalid email (could not fix): {email_input}")
            return None
    
    return email

def clean_text_field(text_input: Any) -> Optional[str]:
    """
    Clean a text field by removing extra whitespace, fixing capitalization, etc.
    
    Args:
        text_input: Text string or other input to clean
        
    Returns:
        Cleaned text or None if input is invalid
    """
    # Handle None, NaN, empty strings
    if text_input is None or pd.isna(text_input) or (isinstance(text_input, str) and not text_input.strip()):
        return None
    
    # Convert to string if not already
    if not isinstance(text_input, str):
        try:
            text_input = str(text_input)
        except:
            return None
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text_input).strip()
    
    # Fix capitalization for sentences
    if text and len(text) > 0:
        # Capitalize first letter of each sentence
        text = re.sub(r'(^|[.!?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), text)
    
    return text

def standardize_postcode(postcode_input: Any) -> Optional[str]:
    """
    Standardize UK postcodes to correct format.
    
    Args:
        postcode_input: Postcode string or other input to standardize
        
    Returns:
        Formatted postcode or None if input is invalid
    """
    # Handle None, NaN, empty strings
    if postcode_input is None or pd.isna(postcode_input) or (isinstance(postcode_input, str) and not postcode_input.strip()):
        return None
    
    # Convert to string if not already
    if not isinstance(postcode_input, str):
        try:
            postcode_input = str(postcode_input)
        except:
            return None
    
    # Remove all whitespace and convert to uppercase
    postcode = re.sub(r'\s', '', postcode_input).upper()
    
    # Validate with UK postcode pattern
    uk_pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$'
    if not re.match(uk_pattern, postcode):
        logger.warning(f"Invalid UK postcode: {postcode_input}")
        return None
    
    # Format with a space in the correct position
    formatted = postcode[:-3] + ' ' + postcode[-3:]
    
    return formatted

def standardize_numeric(numeric_input: Any) -> Optional[float]:
    """
    Standardize numeric values, handling different formats.
    
    Args:
        numeric_input: Numeric string, int, float or other input to standardize
        
    Returns:
        Standardized numeric value as float or None if input is invalid
    """
    # Handle None, NaN, empty strings
    if numeric_input is None or pd.isna(numeric_input) or (isinstance(numeric_input, str) and not numeric_input.strip()):
        return None
    
    # If already a number, return as float
    if isinstance(numeric_input, (int, float)):
        return float(numeric_input)
    
    # Convert to string if not already
    if not isinstance(numeric_input, str):
        try:
            numeric_input = str(numeric_input)
        except:
            return None
    
    # Remove currency symbols, commas, and extra spaces
    cleaned = re.sub(r'[£$€,\s]', '', numeric_input)
    
    # Try to convert to float
    try:
        return float(cleaned)
    except ValueError:
        logger.warning(f"Could not convert to numeric value: {numeric_input}")
        return None

# Import pandas here to avoid circular imports
import pandas as pd 