"""
Pattern configuration for document filtering.

These patterns are used by DrawingPatternMatcher to identify
planning drawing documents (site plans, floor plans, elevations, etc.)
"""

from typing import List, Dict

# =============================================================================
# Drawing Include Patterns
# =============================================================================
# Patterns that indicate a document is a planning drawing

DRAWING_INCLUDE_PATTERNS: Dict[str, List[str]] = {
    # Site plans
    "site_plan": [
        r"\bsite\s*plan",
        r"\bsite\s*layout",
        r"\blocation\s*plan",
        r"\bblock\s*plan",
    ],
    # Floor plans
    "floor_plan": [
        r"\bfloor\s*plan",
        r"\bground\s*floor",
        r"\bfirst\s*floor",
        r"\bsecond\s*floor",
        r"\bbasement",
        r"\bloft\s*plan",
        r"\battic\s*plan",
        r"\blayout\s*plan",
        r"\bproposed\s*plan",
        r"\bexisting\s*plan",
    ],
    # Elevations
    "elevation": [
        r"\belevation",
        r"\bfront\s*elevation",
        r"\brear\s*elevation",
        r"\bside\s*elevation",
        r"\bnorth\s*elevation",
        r"\bsouth\s*elevation",
        r"\beast\s*elevation",
        r"\bwest\s*elevation",
        r"\bstreet\s*elevation",
    ],
    # Sections
    "section": [
        r"\bsection",
        r"\bcross\s*section",
        r"\blongitudinal",
    ],
    # Roof plans
    "roof_plan": [
        r"\broof\s*plan",
        r"\broof\s*layout",
    ],
    # Other drawings
    "drawing": [
        r"\bdrawing",
        r"\bplan\b(?!ning)",  # "plan" but not "planning"
        r"\bproposed\s*dwg",
        r"\bexisting\s*dwg",
        r"\bga\s*plan",  # General arrangement
        r"\bgeneral\s*arrangement",
    ],
}

# Flattened list of all include patterns
DRAWING_INCLUDE_FLAT: List[str] = [
    pattern for patterns in DRAWING_INCLUDE_PATTERNS.values() for pattern in patterns
]


# =============================================================================
# Drawing Exclude Patterns
# =============================================================================
# Patterns that indicate a document is NOT a drawing (forms, statements, etc.)

DRAWING_EXCLUDE_PATTERNS: List[str] = [
    # Forms and applications
    r"\bapplication\s*form",
    r"\bplanning\s*form",
    r"\bsubmission\s*form",
    r"\bconsent\s*form",
    r"\bnotification\s*form",
    # Statements and reports
    r"\bdesign\s*(and|&)\s*access\s*statement",
    r"\bd\s*&\s*a\s*statement",
    r"\bheritage\s*statement",
    r"\bplanning\s*statement",
    r"\bstatement",
    r"\breport\b",
    r"\bassessment\b",
    r"\bsurvey\b",
    r"\bstudy\b",
    r"\banalysis\b",
    # Letters and correspondence
    r"\bletter\b",
    r"\bcorrespondence",
    r"\bemail\b",
    r"\bconsultation\s*response",
    r"\brepresentation",
    # Decision documents
    r"\bdecision\s*notice",
    r"\brefusal",
    r"\bapproval",
    r"\bpermission",
    r"\bconditions",
    # Photos and non-drawings
    r"\bphoto",
    r"\bphotograph",
    r"\bimage\b",
    # Other non-drawings
    r"\bcertificate",
    r"\bdeclaration",
    r"\bagenda",
    r"\bminutes",
    r"\bcomment",
    r"\bobjection",
    r"\bsupport\s*letter",
    r"\bcovering\s*letter",
    r"\bvalidation",
    r"\bchecklist",
]


# =============================================================================
# Application Type Patterns
# =============================================================================
# Patterns for identifying residential/householder applications

RESIDENTIAL_APPLICATION_TYPES: List[str] = [
    "householder",
    "domestic",
    "house holder",
    "dwelling",
    "residential",
    "full application",
    "full planning",
]

RESIDENTIAL_PROPOSAL_KEYWORDS: List[str] = [
    "extension",
    "loft conversion",
    "dormer",
    "conservatory",
    "garage",
    "annexe",
    "annex",
    "outbuilding",
    "porch",
    "single storey",
    "two storey",
    "rear extension",
    "side extension",
    "front extension",
    "kitchen extension",
    "roof extension",
    "basement",
    "dwelling",
    "bungalow",
    "house",
    "residential",
    "alterations",
    "refurbishment",
]

COMMERCIAL_EXCLUSION_KEYWORDS: List[str] = [
    "commercial",
    "industrial",
    "retail",
    "office",
    "warehouse",
    "factory",
    "business",
    "shop",
    "store",
    "agricultural",
    "farm",
    "hotel",
    "restaurant",
    "pub",
    "school",
    "hospital",
    "church",
    "mosque",
    "temple",
    "care home",
    "nursing home",
    "student accommodation",
]
