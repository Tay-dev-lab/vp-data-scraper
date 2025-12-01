import re
import requests
import urllib.parse
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AddressProcessor:
    """
    Process UK addresses by parsing them into components using PyPostal service.
    """
    
    def __init__(self, service_url="http://pypostal-service:4400"):
        """Initialize with the URL of the PyPostal service."""
        self.service_url = service_url
        logger.info(f"AddressProcessor initialized with service URL: {service_url}")
    
    def _parse_with_pypostal(self, address_string):
        """
        Parse address using PyPostal service with GET request and query parameters.
        Returns parsed components or None if parsing fails.
        """
        if not address_string:
            return None
            
        try:
            # URL encode the address for query string
            encoded_address = urllib.parse.quote(address_string)
            url = f"{self.service_url}/parse?address={encoded_address}"
            
            response = requests.get(url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"PyPostal error: Status code {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error connecting to PyPostal service: {str(e)}")
            return None
    
    def _extract_uk_postcode(self, address_string):
        """
        Extract UK postcode from address string.
        
        Args:
            address_string: Address string to extract postcode from
            
        Returns:
            Extracted postcode or None if not found
        """
        # Handle None or NaN values
        if address_string is None or pd.isna(address_string):
            return None
        
        # Convert to string if it's not already
        if not isinstance(address_string, str):
            address_string = str(address_string)
        
        # UK postcode regex pattern
        pattern = r'[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}'
        
        match = re.search(pattern, address_string.upper())
        if match:
            # Format postcode with proper spacing
            postcode = match.group(0).strip()
            if ' ' not in postcode and len(postcode) > 5:
                # Add space in the right position if missing
                postcode = postcode[:-3] + ' ' + postcode[-3:]
            return postcode
        
        return None
    
    def _capitalize_address(self, text):
        """Properly capitalize address components."""
        if not text:
            return None
            
        # Special cases for UK addresses
        special_cases = {
            'uk': 'UK',
            'road': 'Road',
            'street': 'Street',
            'st': 'St',
            'avenue': 'Avenue',
            'ave': 'Ave',
            'lane': 'Lane',
            'ln': 'Ln',
            'drive': 'Drive',
            'dr': 'Dr',
            'court': 'Court',
            'ct': 'Ct',
            'place': 'Place',
            'pl': 'Pl',
            'upon': 'upon',  # for names like "Newcastle upon Tyne"
        }
        
        # Split by spaces and capitalize each word
        words = text.split()
        result = []
        
        for word in words:
            # Check for possessive apostrophes (e.g., King's Road)
            if "'" in word and word.lower() not in special_cases:
                parts = word.split("'")
                word = parts[0].capitalize() + "'" + parts[1]
            # Apply special case or capitalize
            elif word.lower() in special_cases:
                word = special_cases[word.lower()]
            else:
                word = word.capitalize()
            
            result.append(word)
        
        return ' '.join(result)
    
    def process_address(self, address_string):
        """
        Process an address string to extract structured components.
        
        Args:
            address_string: Address string to process
            
        Returns:
            Dictionary with address components from libpostal
        """
        # Initialize result with original address
        result = {
            'full_address': address_string
        }
        
        # Handle None or NaN values
        if address_string is None or pd.isna(address_string):
            return result
        
        # Convert to string if it's not already
        if not isinstance(address_string, str):
            address_string = str(address_string)

        # Clean up the address string - remove trailing commas and extra whitespace
        cleaned_address = re.sub(r',\s*$', '', address_string.strip())
        # Also remove any consecutive commas and replace with a single comma
        cleaned_address = re.sub(r',\s*,+', ',', cleaned_address)
        # Remove any spaces before commas
        cleaned_address = re.sub(r'\s+,', ',', cleaned_address)
        
        # Log the cleaning if it made a difference
        if cleaned_address != address_string:
            logger.debug(f"Cleaned address: '{address_string}' -> '{cleaned_address}'")

        # Try to use pypostal service if available
        try:
            # Get parsed components from PyPostal
            parsed = self._parse_with_pypostal(cleaned_address)
            
            if parsed:
                # Add each component directly to the result dictionary 
                for item in parsed:
                    label = item['label']
                    value = item['value']
                    
                    # Apply capitalization for text fields (except postcode)
                    if label != 'postcode':
                        value = self._capitalize_address(value)
                    else:
                        value = value.upper()
                        
                    result[label] = value
            else:
                logger.warning(f"PyPostal returned no results for: {cleaned_address}")
            
            # # Extract postcode using regex as fallback if not present
            # if 'postcode' not in result:
            #     postcode = self._extract_uk_postcode(address_string)
            #     if postcode:
            #         result['postcode'] = postcode
            
        except Exception as e:
            logger.error(f"Error connecting to PyPostal service: {e}")
            # Extract postcode using regex as fallback
            postcode = self._extract_uk_postcode(address_string)
            if postcode:
                result['postcode'] = postcode.upper()
        
        logger.debug(f"Final processed address: {result}")
        return result