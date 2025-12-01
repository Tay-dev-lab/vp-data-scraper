import re
import logging
from typing import Dict, Any, Optional, Union
from tabulate import tabulate
import csv
import os

logger = logging.getLogger(__name__)

class ProposalCategoriser:
    """
    A class for categorizing planning proposals using regex pattern matching.
    
    This categorizer identifies:
    - Residential developments with unit counts
    - Commercial developments with unit counts
    - Mixed-use developments (both residential and commercial)
    - Householder developments (extensions, loft conversions, etc.)
    - Conversions (barn conversions, commercial-to-residential, etc.)
    """
    
    def __init__(self):
        """Initialize the ProposalCategoriser with compiled regex patterns for efficiency."""
        # Compile regex patterns for better performance
        # Update the residential units pattern to better catch single dwellings
        self.residential_units_pattern = re.compile(
            r'(\d+)(?:\s*no\.?|\s+number\s+of)?\s*(?:dwelling|home|house|flat|apartment|maisonette|studio|residential unit|self-contained|self contained|self-build|self build)s?',
            re.IGNORECASE
        )
        
        # Pattern specifically for single dwellings
        self.single_dwelling_pattern = re.compile(
            r'(\d+)\s+(?:dwelling|home|house|residential unit)(?!\s*s)',  # Match number + dwelling but not followed by 's'
            re.IGNORECASE
        )
        
        # Keep the replacement dwelling pattern for specific cases
        self.replacement_dwelling_pattern = re.compile(
            r'replacement\s+dwelling|demolition\s+and\s+rebuild|demolish\s+and\s+rebuild|demolish\s+existing\s+and\s+erect',
            re.IGNORECASE
        )
        
        self.commercial_units_pattern = re.compile(
            r'(\d+)(?:\s*no\.?|\s+number\s+of)?\s*(?:commercial|retail|office|shop|restaurant|café|cafe|store|business|industrial|unit|class e|use class e)',
            re.IGNORECASE
        )
        
        self.mixed_use_pattern = re.compile(
            r'mixed use|mixed-use|residential and commercial|commercial and residential',
            re.IGNORECASE
        )
        
        self.extension_pattern = re.compile(
            r'extension|conservatory|orangery|addition|rear|side|front extension|two-storey|two storey|single storey|first floor|ground floor extension',
            re.IGNORECASE
        )
        
        self.loft_conversion_pattern = re.compile(
            r'loft\s+conversion|roof\s+extension|dormer|skylight|velux|roof\s+window|roof light|rooflight',
            re.IGNORECASE
        )
        
        self.other_householder_pattern = re.compile(
            r'garage conversion|outbuilding|garden room|porch|window|solar panel',
            re.IGNORECASE
        )
        
        self.barn_conversion_pattern = re.compile(
            r'(?:barn|agricultural building|farm building)\s+(?:conversion|to|into)|agricultural(?:\s+\w+)?\s+to\s+(?:residential|dwelling|house|flat)',
            re.IGNORECASE
        )
        
        self.commercial_to_residential_pattern = re.compile(
            r'(?:office|commercial|retail|shop|industrial|business|class e|storage|warehouse|b1|b2|b8)\s+(?:to|conversion to|into)\s+(?:residential|dwelling|flat|apartment|house|c3)',
            re.IGNORECASE
        )
        
        self.general_conversion_pattern = re.compile(
            r'conversion of|change of use from|from\s+\w+\s+to\s+\w+',
            re.IGNORECASE
        )
        
        self.single_family_dwelling_pattern = re.compile(
            r'(\d+)(?:\s*no\.?|\s+number\s+of)?\s*(?:single family dwelling|family dwelling|family home)',
            re.IGNORECASE
        )
    
    def diagnose_pattern_matches(self, text: str) -> Dict[str, bool]:
        """
        Diagnose which patterns match for a given text.
        
        Args:
            text: The proposal text to check
            
        Returns:
            dict: A dictionary of pattern names and whether they match
        """
        text_lower = text.lower()
        return {
            "residential_units": bool(self.residential_units_pattern.search(text_lower)),
            "commercial_units": bool(self.commercial_units_pattern.search(text_lower)),
            "mixed_use": bool(self.mixed_use_pattern.search(text_lower)),
            "extension": bool(self.extension_pattern.search(text_lower)),
            "loft_conversion": bool(self.loft_conversion_pattern.search(text_lower)),
            "other_householder": bool(self.other_householder_pattern.search(text_lower)),
            "barn_conversion": bool(self.barn_conversion_pattern.search(text_lower)),
            "commercial_to_residential": bool(self.commercial_to_residential_pattern.search(text_lower)),
            "general_conversion": bool(self.general_conversion_pattern.search(text_lower)),
            "single_family_dwelling": bool(self.single_family_dwelling_pattern.search(text_lower)),
        }
    
    def format_currency(self, value: Union[int, float]) -> str:
        """
        Format a number as a GBP currency string with commas.
        
        Args:
            value: The numeric value to format
            
        Returns:
            str: Formatted currency string with £ symbol
        """
        return f"£{value:,.0f}"

    def calculate_estimated_value(self, units: int) -> str:
        """
        Calculate estimated value range based on number of units.
        
        Args:
            units: Number of residential units
            
        Returns:
            str: Formatted value range (e.g., "£500,000 - £1,000,000")
        """
        if units <= 0:
            return "£0"
        
        lower_estimate = units * 100000
        upper_estimate = units * 200000
        
        return f"{self.format_currency(lower_estimate)} - {self.format_currency(upper_estimate)}"

    def categorize_proposal(self, text: Optional[str]) -> Dict[str, Any]:
        """
        Categorize a planning proposal based on simplified pattern matching.
        
        Args:
            text: The proposal text to categorize
            
        Returns:
            dict: A dictionary containing categorization details
        """
        # Initialize result with default values
        result = {
            "category": "uncategorized",
            "residential_units": 0,
            "commercial_units": 0,
            "is_householder": False,
            "householder_type": None,
            "is_conversion": False,
            "conversion_type": None,
            "description": text,
            "estimated_value": "£0"  # Initialize with £0
        }
        
        # Handle None or empty text
        if not text or not isinstance(text, str):
            logger.warning(f"Invalid proposal text: {text}")
            return result
        
        try:
            text_lower = text.lower()
            
            # STEP 1: Extract units (regardless of category)
            res_match = self.residential_units_pattern.search(text_lower)
            if res_match:
                result["residential_units"] = int(res_match.group(1))
                logger.debug(f"Found {result['residential_units']} residential units in: {text[:100]}...")
            
            # Check specifically for single dwelling pattern
            single_match = self.single_dwelling_pattern.search(text_lower)
            if single_match:
                units = int(single_match.group(1))
                if units == 1:  # Ensure it's a single dwelling
                    result["residential_units"] = 1
                    result["category"] = "residential"
                    logger.debug(f"Found single dwelling in: {text[:100]}...")
            
            comm_match = self.commercial_units_pattern.search(text_lower)
            if comm_match:
                result["commercial_units"] = int(comm_match.group(1))
                logger.debug(f"Found {result['commercial_units']} commercial units in: {text[:100]}...")
            
            # STEP 2: Determine category based on simplified rules
            
            # Check for replacement dwelling
            if self.replacement_dwelling_pattern.search(text_lower):
                result["category"] = "residential"
                # Set residential units to 1 if not already set
                if result["residential_units"] == 0:
                    result["residential_units"] = 1
            
            # Check for loft conversion
            elif "loft conversion" in text_lower:
                result["is_householder"] = True
                result["householder_type"] = "loft_conversion"
                result["category"] = "householder_development"
                # Set residential units to 1 for householder developments
                result["residential_units"] = 1
            
            # Simplified conversion check
            elif "conversion" in text_lower or "change of use" in text_lower:
                result["is_conversion"] = True
                result["category"] = "conversion"
                
                # Determine conversion type
                if "barn" in text_lower or "agricultural" in text_lower or "farm" in text_lower:
                    result["conversion_type"] = "barn_to_residential"
                    # Set residential units to 1 for barn conversions to residential
                    if "residential" in text_lower or "dwelling" in text_lower:
                        result["residential_units"] = max(1, result["residential_units"])
                elif ("office" in text_lower or "commercial" in text_lower or "retail" in text_lower or 
                      "shop" in text_lower or "business" in text_lower) and \
                     ("residential" in text_lower or "dwelling" in text_lower or "flat" in text_lower or 
                      "apartment" in text_lower or "house" in text_lower):
                    result["conversion_type"] = "commercial_to_residential"
                    # Set residential units to 1 for commercial to residential conversions
                    result["residential_units"] = max(1, result["residential_units"])
                else:
                    result["conversion_type"] = "other"
                    # If conversion mentions residential, set at least 1 unit
                    if "residential" in text_lower or "dwelling" in text_lower:
                        result["residential_units"] = max(1, result["residential_units"])
            
            # If not already categorized, check other categories
            elif self.mixed_use_pattern.search(text_lower):
                result["category"] = "mixed_use"
            elif result["residential_units"] > 0 and result["commercial_units"] > 0:
                result["category"] = "mixed_use"
            elif result["residential_units"] > 0:
                result["category"] = "residential"
            elif result["commercial_units"] > 0:
                result["category"] = "commercial"
            
            # Check for other householder developments (only if not already categorized)
            if result["category"] == "uncategorized":
                if self.extension_pattern.search(text_lower):
                    result["is_householder"] = True
                    result["householder_type"] = "extension"
                    result["category"] = "householder_development"
                    # Set residential units to 1 for householder developments
                    result["residential_units"] = 1
                elif self.loft_conversion_pattern.search(text_lower) and "loft conversion" not in text_lower:
                    result["is_householder"] = True
                    result["householder_type"] = "loft_conversion"
                    result["category"] = "householder_development"
                    # Set residential units to 1 for householder developments
                    result["residential_units"] = 1
                elif self.other_householder_pattern.search(text_lower):
                    result["is_householder"] = True
                    result["householder_type"] = "other"
                    result["category"] = "householder_development"
                    # Set residential units to 1 for householder developments
                    result["residential_units"] = 1
            
            # Special case for single family dwellings (if still uncategorized)
            if single_family_match := self.single_family_dwelling_pattern.search(text_lower):
                result["residential_units"] = int(single_family_match.group(1))
                if result["category"] == "uncategorized":
                    result["category"] = "residential"
            
            # Final check: if we have a single dwelling mentioned but no category yet, mark as residential
            if "1 dwelling" in text_lower or "one dwelling" in text_lower:
                if result["category"] == "uncategorized":
                    result["category"] = "residential"
                if result["residential_units"] == 0:
                    result["residential_units"] = 1
        
        except Exception as e:
            logger.error(f"Error categorizing proposal: {e}")
            logger.error(f"Problematic text: {text[:200]}...")
        
        # Final check: ensure all householder developments have at least 1 residential unit
        if result["is_householder"] and result["residential_units"] == 0:
            result["residential_units"] = 1
        
        # Ensure conversions to residential have at least 1 residential unit
        if result["is_conversion"] and "residential" in text_lower and result["residential_units"] == 0:
            result["residential_units"] = 1
        
        # Calculate estimated value based on residential units
        result["estimated_value"] = self.calculate_estimated_value(result["residential_units"])
        
        return result
    
    def debug_categorization(self, texts, output_file=None):
        """
        Debug categorization for multiple texts and display results in a CSV file.
        
        Args:
            texts: List of texts to categorize
            output_file: Path to save CSV output file (if None, uses 'proposal_debug.csv' in current directory)
            
        Returns:
            str: Summary table and path to output file
        """
        if output_file is None:
            # Save to current directory instead of /tmp/
            output_file = os.path.join(os.getcwd(), "proposal_debug.csv")
        
        results = []
        pattern_names = None
        
        for text in texts:
            # Get pattern matches
            pattern_results = self.diagnose_pattern_matches(text)
            
            # Store pattern names on first iteration for later use
            if pattern_names is None:
                pattern_names = list(pattern_results.keys())
            
            # Get categorization result
            result = self.categorize_proposal(text)
            
            # Combine information
            row = {
                "Text": text,
                "Category": result["category"],
                "Conversion Type": result["conversion_type"] or "N/A",
                "Residential Units": result["residential_units"],
                "Commercial Units": result["commercial_units"],
                "Is Conversion": "Yes" if result["is_conversion"] else "No",
                "Is Householder": "Yes" if result["is_householder"] else "No",
                "Householder Type": result["householder_type"] or "N/A",
                "Estimated Value": result["estimated_value"],  # Add estimated value to debug output
            }
            
            # Add pattern match results
            for pattern, match_result in pattern_results.items():
                row[f"Pattern: {pattern}"] = "Yes" if match_result else "No"
            
            results.append(row)
        
        # Define headers
        headers = [
            "Text", 
            "Category", 
            "Conversion Type", 
            "Residential Units",
            "Commercial Units", 
            "Is Conversion", 
            "Is Householder",
            "Householder Type",
            "Estimated Value"  # Add to headers
        ]
        
        # Add pattern headers
        pattern_headers = [f"Pattern: {pattern}" for pattern in pattern_names]
        headers.extend(pattern_headers)
        
        # Generate CSV file
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        
        # Return a simplified table for console display
        simple_headers = ["Text", "Category", "Conversion Type", "Residential Units", "Commercial Units", "Is Conversion", "Is Householder", "Estimated Value"]
        simple_table_data = [[row[header] for header in simple_headers] for row in results]
        
        summary = f"Full results saved to {output_file}\n\n"
        summary += tabulate(simple_table_data, headers=simple_headers, tablefmt="grid")
        
        return summary 