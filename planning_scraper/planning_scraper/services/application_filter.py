"""
Service to filter planning applications to residential/householder developments only.

Target application types:
- Extensions and alterations
- Refurbishments
- Loft conversions
- Small new build developments (up to 10 houses or 20 apartments)
"""

import re
from typing import Optional


class ResidentialApplicationFilter:
    """Filter to keep only residential/householder planning applications."""

    # Application types to INCLUDE
    INCLUDE_TYPES = [
        r"\bhouseholder\b",
        r"\bdomestic\b",
        r"\bresidential\b",
        r"\bdwelling\b",
        r"\bfull\s+application\b",  # Often residential
        r"\bfull\s+planning\b",
    ]

    # Proposal keywords to INCLUDE
    INCLUDE_PROPOSAL_KEYWORDS = [
        r"\bextension\b",
        r"\balteration[s]?\b",
        r"\brefurbishment\b",
        r"\bloft\s+conversion\b",
        r"\bconversion\b",
        r"\bsingle\s+storey\b",
        r"\btwo\s+storey\b",
        r"\brear\s+extension\b",
        r"\bside\s+extension\b",
        r"\bgarage\b",
        r"\bconservatory\b",
        r"\bdormer\b",
        r"\boutbuilding\b",
        r"\bporch\b",
        r"\bannex[e]?\b",
        r"\bsummer\s*house\b",
        r"\bgarden\s+room\b",
        r"\b(new\s+)?(dwelling|house|home|flat|apartment)\b",
        r"\broof\b",
        r"\bwindow[s]?\b",
        r"\bdoor[s]?\b",
        r"\bfence\b",
        r"\bwall\b",
        r"\bdeck(ing)?\b",
        r"\bpatio\b",
        r"\bdriveway\b",
        r"\bcarport\b",
    ]

    # Application types/proposals to EXCLUDE
    EXCLUDE_PATTERNS = [
        r"\bcommercial\b",
        r"\bindustrial\b",
        r"\bretail\b",
        r"\boffice[s]?\b",
        r"\btelecommunications?\b",
        r"\badvertisement\b",
        r"\btree\s+works\b",
        r"\btree\s+preservation\b",
        r"\bprior\s+approval\b",  # Usually agricultural
        r"\bagricultural\b",
        r"\bfarm\b",
        r"\bwarehouse\b",
        r"\bfactory\b",
        r"\bschool\b",
        r"\bhospital\b",
        r"\bchurch\b",
        r"\bpub\b",
        r"\brestaurant\b",
        r"\bcafe\b",
        r"\bhotel\b",
        r"\bstudent\s+accommodation\b",
        r"\bcare\s+home\b",
        r"\bnursing\s+home\b",
        r"\bchange\s+of\s+use\b.*\b(shop|office|commercial|retail)\b",
        r"\bdemolition\b(?!.*\b(and|with)\s+(erection|construction|building))",  # Demolition only
        r"\bwind\s+turbine\b",
        r"\bsolar\s+farm\b",
        r"\bsubstation\b",
    ]

    # Max units for small new builds
    MAX_HOUSES = 10
    MAX_APARTMENTS = 20

    def __init__(
        self,
        include_types: Optional[list] = None,
        include_keywords: Optional[list] = None,
        exclude_patterns: Optional[list] = None,
        max_houses: int = 10,
        max_apartments: int = 20,
    ):
        """
        Initialize the filter with optional custom patterns.

        Args:
            include_types: Custom application type patterns to include
            include_keywords: Custom proposal keywords to include
            exclude_patterns: Custom patterns to exclude
            max_houses: Maximum number of houses for new builds (default 10)
            max_apartments: Maximum number of apartments for new builds (default 20)
        """
        self.include_types = include_types or self.INCLUDE_TYPES
        self.include_keywords = include_keywords or self.INCLUDE_PROPOSAL_KEYWORDS
        self.exclude_patterns = exclude_patterns or self.EXCLUDE_PATTERNS
        self.max_houses = max_houses
        self.max_apartments = max_apartments

        # Pre-compile regex patterns for performance
        self._compiled_include_types = [
            re.compile(p, re.IGNORECASE) for p in self.include_types
        ]
        self._compiled_include_keywords = [
            re.compile(p, re.IGNORECASE) for p in self.include_keywords
        ]
        self._compiled_exclude = [
            re.compile(p, re.IGNORECASE) for p in self.exclude_patterns
        ]

    def is_residential(
        self, application_type: Optional[str], proposal: Optional[str]
    ) -> bool:
        """
        Check if an application is a residential/householder development.

        Args:
            application_type: The application type field (e.g., "Householder", "Full")
            proposal: The proposal/description text

        Returns:
            True if the application appears to be residential/householder
        """
        app_type = (application_type or "").strip()
        prop = (proposal or "").strip()

        # Check exclusions first - if any match, reject
        for pattern in self._compiled_exclude:
            if pattern.search(app_type) or pattern.search(prop):
                return False

        # Check application type - if matches residential type, accept
        for pattern in self._compiled_include_types:
            if pattern.search(app_type):
                return True

        # Check proposal keywords
        for pattern in self._compiled_include_keywords:
            if pattern.search(prop):
                # For new builds, check unit count
                if self._is_new_build(prop):
                    return self._check_unit_count(prop)
                return True

        # No match found - default to rejecting
        return False

    def _is_new_build(self, proposal: str) -> bool:
        """Check if proposal describes a new build development."""
        new_build_patterns = [
            r"\berection\s+of\b",
            r"\bconstruction\s+of\b",
            r"\bnew\s+(dwelling|house|home|flat|apartment|residential)\b",
            r"\b\d+\s+(dwelling|house|home|flat|apartment|unit)s?\b",
        ]
        prop_lower = proposal.lower()
        return any(re.search(p, prop_lower) for p in new_build_patterns)

    def _check_unit_count(self, proposal: str) -> bool:
        """
        Check if a new build is within small development limits.

        Returns True if:
        - No unit count found (assume small)
        - Houses/dwellings count <= max_houses
        - Flats/apartments count <= max_apartments
        """
        prop_lower = proposal.lower()

        # Extract numbers associated with unit types
        unit_patterns = [
            r"(\d+)\s*(dwelling|house|home|bungalow)s?",
            r"(\d+)\s*(flat|apartment|unit)s?",
            r"(\d+)\s*(?:no\.?\s*)?(dwelling|house|home|flat|apartment|unit)s?",
        ]

        for pattern in unit_patterns:
            matches = re.findall(pattern, prop_lower)
            if matches:
                for count_str, unit_type in matches:
                    count = int(count_str)
                    if unit_type in ("flat", "apartment"):
                        if count > self.max_apartments:
                            return False
                    else:
                        if count > self.max_houses:
                            return False

        # Also check for written numbers
        written_numbers = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        for word, num in written_numbers.items():
            if re.search(rf"\b{word}\s+(dwelling|house|flat|apartment)s?\b", prop_lower):
                if num > self.max_houses:
                    return False

        return True  # No unit count found or within limits

    def get_rejection_reason(
        self, application_type: Optional[str], proposal: Optional[str]
    ) -> Optional[str]:
        """
        Get the reason why an application would be rejected.

        Returns None if the application would be accepted.
        """
        app_type = (application_type or "").strip()
        prop = (proposal or "").strip()

        # Check exclusions
        for pattern in self._compiled_exclude:
            if pattern.search(app_type):
                return f"Application type matches exclusion pattern: {pattern.pattern}"
            if pattern.search(prop):
                return f"Proposal matches exclusion pattern: {pattern.pattern}"

        # Check if residential
        if self.is_residential(application_type, proposal):
            return None

        return "No residential/householder patterns matched"
