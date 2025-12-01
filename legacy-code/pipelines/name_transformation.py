import gender_guesser.detector as gender
from nameparser import HumanName
import probablepeople as pp
import re
import requests
import urllib.parse
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NameProcessor:
    def __init__(self):
        self.gender_detector = gender.Detector(case_sensitive=False)
        
        # ADD THIS: Company name indicators
        self.company_indicators = [
            r'\bLLC\b',
            r'\bInc\b',
            r'\bLtd\b',
            r'\bLimited\b',
            r'\bCorp\b',
            r'\bCorporation\b',
            r'\bCompany\b',
            r'\bCo\b',
            r'\bPlc\b',
            r'\bLLP\b',
            r'\bGroup\b',
            r'\bHoldings\b',
            r'\bAssociates\b',
            r'\b& Sons\b',
            r'\bconsult\b',
            r'\bArchitects\b',
            r'\bArchitecture\b',
            r'\bDesign\b',
        ]
        
        # Strong company identifiers that almost always indicate a company
        self.company_suffixes = [
            'ltd', 'limited', 'llc', 'inc', 'incorporated', 'corp', 'corporation',
            'plc', 'holdings', 'group', 'associates', 'partnership', 'partners',
            'consulting', 'consultants', 'services', 'solutions', 'international',
            'uk', 'co ltd', 'and co', '& co', 'company', 'gmbh', 'sa', 'ag'
        ]
        
        # Business type words that might indicate a company
        self.business_words = [
            'architects', 'construction', 'developers', 'properties', 'property',
            'investments', 'design', 'build', 'homes', 'estate', 'estates',
            'surveyor', 'surveyors', 'engineering', 'engineer', 'consultant',
            'planning', 'management', 'agency', 'project', 'projects', 'consult',
            'association', 'trust', 'council', 'authority', 'department'
        ]
        
        # Common separators between person and company
        self.separators = [
            ' at ', ' from ', ' of ', ' - ', ', ', ' / ', ' for ', ' @ ',
            ' representing ', ' on behalf of '
        ]
    
    def is_company_name(self, name):
        """
        Determine if the name is likely a company name rather than a person's name.
        Uses probablepeople for detection with a fallback to keyword-based detection.
        
        Args:
            name (str): The name to check
            
        Returns:
            bool: True if name is likely a company, False otherwise
        """
        if not name or not isinstance(name, str):
            return False
            
        # Try using probablepeople for classification
        try:
            parsed, entity_type = pp.tag(name)
            return entity_type == 'Corporation'
        except Exception as e:
            # Fall back to keyword detection if probablepeople fails
            logging.debug(f"probablepeople failed on {name}: {e}")
            
            # Check for common company indicators in the name
            name_lower = name.lower()
            for indicator in self.company_indicators:
                if f" {indicator}" in name_lower or name_lower.endswith(f" {indicator}"):
                    return True
            
            # Additional heuristics
            # Check for absence of spaces (likely a single word company name)
            if ' ' not in name and len(name) > 1 and name[0].isupper():
                return True
                
            return False
    
    def parse_company_name(self, name):
        """
        Parse a company name into its components.
        
        Args:
            name (str): The company name to parse
            
        Returns:
            dict: Parsed components of the company name
        """
        try:
            parsed, entity_type = pp.tag(name)
            if entity_type == 'Corporation':
                return parsed
            # If probablepeople thinks it's a person but we believe it's a company
            # just return the name as the corporation name
            return {'CorporationName': name}
        except:
            return {'CorporationName': name}
    
    def extract_company_name(self, text):
        """
        Extract a company name from text using multiple strategies
        
        Returns: Company name or None if no company found
        """
        if not text or not isinstance(text, str):
            return None
            
        text = text.strip()
        text_lower = text.lower()
        
        # Strategy 1: Check for separator patterns (Person at Company)
        for sep in self.separators:
            if sep in text:
                parts = text.split(sep, 1)
                # Check if second part looks like a company
                if self._is_likely_company(parts[1].strip()):
                    return parts[1].strip()
        
        # Strategy 2: Check for company suffix patterns
        for suffix in self.company_suffixes:
            pattern = rf'(.*\s+{suffix}(\s+|$))'
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                # Extract the company name that ends with this suffix
                company_text = text[match.start():match.end()].strip()
                # Don't capture titles like "Mr" or "Dr" in the company name
                title_match = re.match(r'^(mr|mrs|miss|ms|dr|prof|sir)\s+', company_text, re.IGNORECASE)
                if title_match:
                    continue
                return company_text
        
        # Strategy 3: Check if entire string looks like a company
        if self._is_likely_company(text):
            return text
            
        return None
    
    def _is_likely_company(self, text):
        """Determine if text is likely a company name"""
        if not text:
            return False
            
        text_lower = text.lower()
        
        # Check for company suffixes
        for suffix in self.company_suffixes:
            suffix_pattern = rf'\s{suffix}(\s|$)'
            if re.search(suffix_pattern, text_lower):
                return True
        
        # Check for business words
        for word in self.business_words:
            word_pattern = rf'(\b{word}\b)'
            if re.search(word_pattern, text_lower):
                return True
                
        # Additional heuristic: Multiple capitalized words without personal titles
        # suggests organization rather than person
        words = text.split()
        if (len(words) >= 2 and 
            all(word[0].isupper() for word in words if len(word) > 1) and
            not any(word.lower() in ['mr', 'mrs', 'miss', 'ms', 'dr'] for word in words)):
            return True
            
        return False
    
    def extract_person_name(self, text, company_name=None):
        """
        Extract person name from text, optionally with knowledge of company name.
        
        Returns: Person name or None if no person found
        """
        if not text:
            return None
            
        # If we already identified a company name, remove it from the text
        if company_name and company_name in text:
            # Remove the company name and any separators
            person_text = text.replace(company_name, '').strip()
            for sep in self.separators:
                person_text = person_text.replace(sep, ' ').strip()
                
            # If anything meaningful remains, it might be a person name
            if len(person_text) > 2:
                # Verify it looks like a person name using nameparser
                human = HumanName(person_text)
                if human.first or human.last:
                    return person_text
                return None
        
        # If no company name was found or we couldn't extract a person name,
        # check if the original text looks like a person
        human = HumanName(text)
        
        # Only consider it a person name if it has recognizable person name components
        # and doesn't look like a company
        if (human.first or human.last) and not self._is_likely_company(text):
            return text
            
        return None
    
    def process_name(self, name):
        """
        Process an agent name field, separating company and person names using probablepeople.
        
        Returns: Dictionary with 'person_name' and 'company_name' keys
        """
        result = {
            'person_name': None,
            'company_name': None
        }
        
        if not name or not isinstance(name, str):
            return result
        
        # Check if there's a separator (dash, etc.)
        if ' - ' in name:
            parts = name.split(' - ', 1)
            left_part = parts[0].strip()
            right_part = parts[1].strip()
            
            # Try to classify each part using probablepeople
            try:
                left_parsed, left_type = pp.tag(left_part)
                right_parsed, right_type = pp.tag(right_part)
                
                # If we have a clear company and person
                if left_type == 'Corporation' and right_type == 'Person':
                    result['company_name'] = left_part
                    result['person_name'] = right_part
                    return result
                    
                # If we have a clear person and company
                if right_type == 'Corporation' and left_type == 'Person':
                    result['company_name'] = right_part
                    result['person_name'] = left_part
                    return result
                    
                # If both parts are the same type, use our heuristics
                # Company indicators take precedence
                if self._is_likely_company(left_part) and not self._is_likely_company(right_part):
                    result['company_name'] = left_part
                    result['person_name'] = right_part
                    return result
                    
                if self._is_likely_company(right_part) and not self._is_likely_company(left_part):
                    result['company_name'] = right_part
                    result['person_name'] = left_part
                    return result
                    
                # Default fallback - left is company, right is person
                result['company_name'] = left_part
                result['person_name'] = right_part
                
            except Exception as e:
                # If probablepeople fails, use our heuristics
                logger.debug(f"probablepeople failed on '{name}': {e}")
                
                # Use our fallback methods
                if self._is_likely_company(left_part) and not self._is_likely_company(right_part):
                    result['company_name'] = left_part
                    result['person_name'] = right_part
                elif self._is_likely_company(right_part) and not self._is_likely_company(left_part):
                    result['company_name'] = right_part
                    result['person_name'] = left_part
                else:
                    # Default to first part being company
                    result['company_name'] = left_part
                    result['person_name'] = right_part
        else:
            # No dash separator - try direct classification with probablepeople
            try:
                parsed, entity_type = pp.tag(name)
                
                if entity_type == 'Corporation':
                    result['company_name'] = name
                elif entity_type == 'Person':
                    result['person_name'] = name
                else:
                    # Household or unknown type - use our heuristics
                    if self._is_likely_company(name):
                        result['company_name'] = name
                    else:
                        result['person_name'] = name
                    
            except pp.RepeatedLabelError:
                # Handle specific probablepeople error for ambiguous labels
                # This often happens with company names that look like person names
                if self._is_likely_company(name):
                    result['company_name'] = name
                else:
                    result['person_name'] = name
                    
            except Exception as e:
                # Handle any other exceptions
                logger.debug(f"probablepeople failed on '{name}': {e}")
                
                # Use our heuristics as fallback
                if self._is_likely_company(name):
                    result['company_name'] = name
                else:
                    result['person_name'] = name
        
        return result
    
    def process_name_for_database(self, name, role):
        """
        Process a name for database storage, handling both person and company names.
        
        Args:
            name (str): The name to process
            role (str): Role of the entity ('agent' or 'applicant')
        """
        result = {
            'first_name': None,
            'last_name': None,
            'title': None,
            'middle_name': None,
            'suffix': None,
            'gender': None,
            'agent_company_name': None,
            'applicant_company_name': None
        }
        
        if not name:
            return result
        
        # Process the name and extract company/person components
        extracted = self.process_name(name)
        
        # Store the original full string for debugging
        result['original_name'] = name
        
        # Process company name if present
        if extracted['company_name']:
            if role == 'applicant':
                result['applicant_company_name'] = extracted['company_name']
            else:  # Default to agent
                result['agent_company_name'] = extracted['company_name']
        
        # Process person name if present (using existing method)
        if extracted['person_name']:
            # Use nameparser for person component
            human_name = HumanName(extracted['person_name'])
            
            # Extract components
            result['title'] = human_name.title or None
            result['first_name'] = self.capitalize_name_part(human_name.first) if human_name.first else None
            result['middle_name'] = self.capitalize_name_part(human_name.middle) if human_name.middle else None
            result['last_name'] = self.capitalize_name_part(human_name.last, is_last_name=True) if human_name.last else None
            result['suffix'] = self.capitalize_suffix(human_name.suffix) if human_name.suffix else None
            
            # Add gender
            if result['first_name']:
                result['gender'] = self.detect_gender(result['first_name'])
            
            # Create salutation
            if result['first_name'] and result['last_name']:
                salutation = self.create_salutation(
                    result['title'],
                    result['first_name'],
                    result['last_name'],
                    result['gender']
                )
                
                # Set the appropriate salutation field based on role
                if role == 'applicant':
                    result['applicant_salutation'] = salutation
                else:  # Default to agent
                    result['agent_salutation'] = salutation
        
        return result
    
    def is_multi_person_name(self, name):
        """
        Detect if the name contains multiple people (e.g., "Mr & Mrs Smith").
        """
        if not name or not isinstance(name, str):
            return False
            
        # Common patterns for multi-person names
        patterns = [
            r"^(Mr|Mrs|Ms|Miss)\s+(&|and)\s+(Mr|Mrs|Ms|Miss)",  # Mr & Mrs
            r"^(Mr|Mrs|Ms|Miss)\s+[A-Z][^\s]*\s+(&|and)\s+[A-Z][^\s]*",  # Mr Smith & Jones
            r"^(Mr|Mrs|Ms|Miss)\s+[A-Z]\.?\s+(&|and)\s+[A-Z]\.?\s+[A-Za-z]+",  # Mr J & B Smith
        ]
        
        name = name.strip()
        for pattern in patterns:
            if re.search(pattern, name, re.IGNORECASE):
                return True
                
        return False

    def parse_name(self, name):
        """
        Parse a name using nameparser first.
        For single-word names, use probablepeople to determine if it's a first or last name.
        For multi-person names, preserve the original format.
        """
        if not name or not isinstance(name, str):
            return {'title': None, 'first': None, 'middle': None, 'last': None, 'suffix': None}
        
        name = name.strip()
        
        # Check if this is a multi-person name pattern
        if self.is_multi_person_name(name):
            # For multi-person names, we want to preserve the entire string
            # and use it directly as the salutation
            return {
                'title': name,  # Store the full name as the title
                'first': None,
                'middle': None,
                'last': None,
                'suffix': None
            }
        
        parsed_hn = HumanName(name)
        
        # Handle single-word name case
        if len(name.split()) == 1 and not any([parsed_hn.title, parsed_hn.suffix]):
            try:
                # Try probablepeople to determine if it's a first or last name
                parsed_pp, type = pp.tag(name)
                
                if 'GivenName' in parsed_pp:
                    return {
                        'title': None,
                        'first': self.capitalize_name_part(name),
                        'middle': None,
                        'last': None,
                        'suffix': None
                    }
                else:
                    # Default to treating it as a last name
                    return {
                        'title': None,
                        'first': None,
                        'middle': None,
                        'last': self.capitalize_name_part(name, is_last_name=True),
                        'suffix': None
                    }
            except:
                # If probablepeople fails, default to last name
                return {
                    'title': None,
                    'first': None,
                    'middle': None,
                    'last': self.capitalize_name_part(name, is_last_name=True),
                    'suffix': None
                }
        
        # Process using nameparser results
        title = parsed_hn.title or None
        first = self.capitalize_name_part(parsed_hn.first) if parsed_hn.first else None
        middle = self.capitalize_name_part(parsed_hn.middle) if parsed_hn.middle else None
        last = self.capitalize_name_part(parsed_hn.last, is_last_name=True) if parsed_hn.last else None
        suffix = self.capitalize_suffix(parsed_hn.suffix)
        
        return {
            'title': title,
            'first': first,
            'middle': middle,
            'last': last,
            'suffix': suffix
        }
    
    def detect_gender(self, first_name):
        """
        Detect likely gender from first name.
        Returns 'unknown' if gender cannot be determined or if first_name is just an initial.
        """
        if not first_name or not isinstance(first_name, str):
            return 'unknown'  # Changed from 'male' to 'unknown'
        
        # Check if the first_name is just an initial (a single letter possibly followed by a period)
        if re.match(r'^[A-Za-z]\.?$', first_name.strip()):
            return 'unknown'  # It's an initial, so gender is unknown
        
        result = self.gender_detector.get_gender(first_name)
        
        if result in ['male', 'mostly_male']:
            return 'male'
        elif result in ['female', 'mostly_female']:
            return 'female'
        else:
            return 'unknown'  # Changed from 'male' to 'unknown'
    
    def process_full_name(self, name):
        """
        Process a name string into its component parts.
        Returns dictionary with salutation, first, middle, last names and full name.
        """
        if not name or not isinstance(name, str):
            return {
                'salutation': None,
                'first_name': None,
                'middle_name': None,
                'last_name': None,
                'suffix': None,
                'co_name': None,
                'full_name': None
            }
            
        name = name.strip()
        
        # Check if it's a multi-person name first
        if self.is_multi_person_name(name):
            # For multi-person names, use the entire name as the salutation
            return {
                'salutation': name,
                'first_name': None,
                'middle_name': None,
                'last_name': None,
                'suffix': None,
                'co_name': None,
                'full_name': name
            }
            
        # Check if it's a company name
        if self.is_company_name(name):
            return {
                'salutation': "Dear Sir/Madam",
                'first_name': None,
                'middle_name': None, 
                'last_name': None, 
                'suffix': None,
                'co_name': name.strip(),  # Store the company name here
                'full_name': name.strip()
            }
            
        # Rest of your existing code for processing person names
        parsed = self.parse_name(name)
        
        # If there's no salutation/title, determine gender and create appropriate salutation
        if not parsed['title']:
            if parsed['last'] and not parsed['first']:
                # Only surname present
                salutation = 'Sir/Madam'
            else:
                gender = self.detect_gender(parsed['first'])
                salutation = self.create_salutation(None, parsed['first'], parsed['last'], gender)
        else:
            # Use existing title to create salutation
            salutation = self.create_salutation(parsed['title'], parsed['first'], parsed['last'], None)
        
        # ADD THIS: Include co_name field (set to None for person names)
        result = {
            'salutation': salutation,
            'first_name': parsed['first'],
            'middle_name': parsed['middle'],
            'last_name': parsed['last'],
            'suffix': parsed['suffix'],
            'co_name': None,  # Add this field
            'full_name': name.strip()
        }
        
        return result
        
    
    def create_salutation(self, title, first_name, last_name, gender):
        """
        Create a salutation based on name components.
        If title contains a full multi-person name, use it directly.
        """
        # If title contains a full multi-person name, use it directly
        if title and self.is_multi_person_name(title):
            return title
            
        # Otherwise, proceed with normal salutation creation
        if not last_name:
            return None
            
        # Existing salutation logic
        if title:
            return f"{title} {last_name}"
            
        if gender == "M":
            return f"Mr {last_name}"
        elif gender == "F":
            return f"Ms {last_name}"
        else:
            # Default salutation when gender is unknown
            if first_name:
                return f"{first_name} {last_name}"
            else:
                return last_name
    
    def capitalize_name_part(self, name_part, is_last_name=False):
        """
        Capitalize a name part according to rules.
        
        Args:
            name_part: The name part to capitalize
            is_last_name: Whether this is a last name (affects capitalization rules)
        
        Returns:
            Capitalized name part
        """
        # Handle None or NaN values
        if name_part is None or pd.isna(name_part):
            return name_part
        
        # Convert to string if it's not already
        if not isinstance(name_part, str):
            name_part = str(name_part)
        
        parts = name_part.split()
        
        # Common European name prefixes that should remain lowercase
        noble_prefixes = ['van', 'von', 'de', 'der', 'den', 'ter', 'ten', 'le', 'la', 'du']
        
        if is_last_name:
            capitalized_parts = []
            
            for i, part in enumerate(parts):
                part_lower = part.lower()
                
                # Handle Mc prefix
                if part_lower.startswith('mc'):
                    capitalized_parts.append(f"Mc{part[2:].title()}")
                # Handle Mac prefix
                elif part_lower.startswith('mac'):
                    capitalized_parts.append(f"Mac{part[3:].title()}")
                # Handle noble prefixes
                elif part_lower in noble_prefixes:
                    capitalized_parts.append(part_lower)
                # Normal capitalization for other parts
                else:
                    capitalized_parts.append(part.title())
            
            return ' '.join(capitalized_parts)
        else:
            # For first and middle names
            if name_part.lower().startswith('mc'):
                return f"Mc{name_part[2:].title()}"
            elif name_part.lower().startswith('mac'):
                return f"Mac{name_part[3:].title()}"
            return name_part.title() 

    def capitalize_suffix(self, suffix):
        """
        Properly capitalize name suffixes.
        """
        if not suffix:
            return None
        
        # Common suffixes that should be all caps
        upper_suffixes = {'phd': 'PhD', 'md': 'MD', 'dds': 'DDS', 'mba': 'MBA'}
        
        # Common generational suffixes
        generational_suffixes = {'jr': 'Jr.', 'sr': 'Sr.', 'ii': 'II', 'iii': 'III', 'iv': 'IV'}
        
        suffix_lower = suffix.lower().replace('.', '')
        
        if suffix_lower in upper_suffixes:
            return upper_suffixes[suffix_lower]
        elif suffix_lower in generational_suffixes:
            return generational_suffixes[suffix_lower]
        
        return suffix.title()

