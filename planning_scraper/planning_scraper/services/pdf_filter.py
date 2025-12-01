"""
Service to filter PDF documents to only planning drawings by filename.

Targets:
- Site plans
- Floor plans
- Elevations
- Block plans
- Location plans
- Sections
- Proposed/existing layouts
"""

import re
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass
class DrawingMatch:
    """Result of a drawing pattern match."""

    is_drawing: bool
    document_type: Optional[str]
    matched_pattern: Optional[str] = None
    confidence: float = 1.0


class DrawingPatternMatcher:
    """Filter PDFs to only planning drawings by filename patterns."""

    # Document type mapping (pattern -> type name)
    TYPE_PATTERNS = {
        r"site[\s_-]?plan": "site_plan",
        r"site[\s_-]?layout": "site_plan",
        r"floor[\s_-]?plan": "floor_plan",
        r"ground[\s_-]?floor": "floor_plan",
        r"first[\s_-]?floor": "floor_plan",
        r"second[\s_-]?floor": "floor_plan",
        r"basement": "floor_plan",
        r"elevation[s]?": "elevation",
        r"front[\s_-]?elevation": "elevation",
        r"rear[\s_-]?elevation": "elevation",
        r"side[\s_-]?elevation": "elevation",
        r"north[\s_-]?elevation": "elevation",
        r"south[\s_-]?elevation": "elevation",
        r"east[\s_-]?elevation": "elevation",
        r"west[\s_-]?elevation": "elevation",
        r"block[\s_-]?plan": "block_plan",
        r"location[\s_-]?plan": "location_plan",
        r"os[\s_-]?location": "location_plan",
        r"red[\s_-]?line[\s_-]?plan": "location_plan",
        r"section[s]?": "section",
        r"cross[\s_-]?section": "section",
        r"roof[\s_-]?plan": "roof_plan",
        r"proposed[\s_-]?plan": "proposed",
        r"proposed[\s_-]?elevation": "proposed",
        r"proposed[\s_-]?layout": "proposed",
        r"existing[\s_-]?plan": "existing",
        r"existing[\s_-]?elevation": "existing",
        r"existing[\s_-]?layout": "existing",
        r"layout[\s_-]?plan": "layout",
        r"ga[\s_-]?plan": "layout",  # General Arrangement
    }

    # Generic patterns that indicate a drawing (lower confidence)
    GENERIC_PATTERNS = [
        r"\bdrawing[s]?\b",
        r"\bplan[s]?\b",
        r"\bdrg\b",
        r"\barchitectural\b",
        r"\blayout\b",
    ]

    # Patterns to EXCLUDE (non-drawing documents)
    EXCLUDE_PATTERNS = [
        r"\bapplication[\s_-]?form\b",
        r"\bplanning[\s_-]?statement\b",
        r"\bdesign[\s_-]?(and[\s_-]?)?access[\s_-]?statement\b",
        r"\bheritage[\s_-]?statement\b",
        r"\btree[\s_-]?survey\b",
        r"\becology[\s_-]?report\b",
        r"\bflood[\s_-]?risk\b",
        r"\btransport[\s_-]?assessment\b",
        r"\bcil[\s_-]?form\b",
        r"\bdecision[\s_-]?notice\b",
        r"\bconsultation\b",
        r"\bofficer[\s_-]?report\b",
        r"\bcommittee[\s_-]?report\b",
        r"\bcovering[\s_-]?letter\b",
        r"\bletter\b",
        r"\bcorrespondence\b",
        r"\bstatement\b",
        r"\breport\b",
        r"\bsurvey\b",
        r"\bphoto[s]?\b",
        r"\bphotograph[s]?\b",
        r"\bimage[s]?\b",
        r"\bnotice\b",
        r"\bform\b",
        r"\bcertificate\b",
        r"\bdeclaration\b",
        r"\bdescription\b",
        r"\bspecification\b",
        r"\bschedule\b",
    ]

    def __init__(
        self,
        type_patterns: Optional[dict] = None,
        generic_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize the pattern matcher with optional custom patterns.

        Args:
            type_patterns: Custom type patterns (pattern -> type name)
            generic_patterns: Custom generic drawing patterns
            exclude_patterns: Custom exclusion patterns
        """
        self.type_patterns = type_patterns or self.TYPE_PATTERNS
        self.generic_patterns = generic_patterns or self.GENERIC_PATTERNS
        self.exclude_patterns = exclude_patterns or self.EXCLUDE_PATTERNS

        # Pre-compile all regex patterns
        self._compiled_types = {
            re.compile(p, re.IGNORECASE): t for p, t in self.type_patterns.items()
        }
        self._compiled_generic = [
            re.compile(p, re.IGNORECASE) for p in self.generic_patterns
        ]
        self._compiled_exclude = [
            re.compile(p, re.IGNORECASE) for p in self.exclude_patterns
        ]

    def is_drawing(self, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a filename represents a planning drawing.

        Args:
            filename: The document filename to check

        Returns:
            Tuple of (is_drawing, document_type)
        """
        match = self.match(filename)
        return match.is_drawing, match.document_type

    def match(self, filename: str) -> DrawingMatch:
        """
        Perform detailed pattern matching on a filename.

        Args:
            filename: The document filename to check

        Returns:
            DrawingMatch with detailed match information
        """
        if not filename:
            return DrawingMatch(is_drawing=False, document_type=None)

        # Normalize filename: remove extension, replace separators
        clean_name = self._normalize_filename(filename)

        # Check exclusions first
        for pattern in self._compiled_exclude:
            if pattern.search(clean_name):
                return DrawingMatch(
                    is_drawing=False,
                    document_type=None,
                    matched_pattern=f"excluded:{pattern.pattern}",
                )

        # Check specific type patterns (high confidence)
        for pattern, doc_type in self._compiled_types.items():
            if pattern.search(clean_name):
                return DrawingMatch(
                    is_drawing=True,
                    document_type=doc_type,
                    matched_pattern=pattern.pattern,
                    confidence=0.95,
                )

        # Check generic patterns (lower confidence)
        for pattern in self._compiled_generic:
            if pattern.search(clean_name):
                return DrawingMatch(
                    is_drawing=True,
                    document_type="drawing",
                    matched_pattern=pattern.pattern,
                    confidence=0.70,
                )

        # No match
        return DrawingMatch(is_drawing=False, document_type=None)

    def _normalize_filename(self, filename: str) -> str:
        """
        Normalize a filename for pattern matching.

        - Removes file extension
        - Replaces underscores and hyphens with spaces
        - Normalizes whitespace
        """
        # Remove extension
        name = re.sub(r"\.[^.]+$", "", filename)
        # Replace separators with spaces
        name = re.sub(r"[_-]+", " ", name)
        # Normalize whitespace
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def get_document_type(self, filename: str) -> Optional[str]:
        """
        Get the document type for a filename if it's a drawing.

        Args:
            filename: The document filename

        Returns:
            Document type string or None if not a drawing
        """
        match = self.match(filename)
        return match.document_type if match.is_drawing else None

    def filter_documents(
        self, filenames: List[str]
    ) -> List[Tuple[str, str]]:
        """
        Filter a list of filenames to only drawings.

        Args:
            filenames: List of document filenames

        Returns:
            List of (filename, document_type) tuples for drawings only
        """
        results = []
        for filename in filenames:
            is_drawing, doc_type = self.is_drawing(filename)
            if is_drawing:
                results.append((filename, doc_type))
        return results
