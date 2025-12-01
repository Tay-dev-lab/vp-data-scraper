"""
Date parsing and standardization utilities.

Handles various UK date formats from planning portals.
"""

import re
from datetime import datetime
from typing import Optional


def standardize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Standardize a date string to YYYY-MM-DD format.

    Handles various formats:
    - DD/MM/YYYY
    - DD-MM-YYYY
    - YYYY-MM-DD
    - DD Mon YYYY (e.g., "15 Jan 2025")
    - DD Month YYYY (e.g., "15 January 2025")
    - ISO format with time

    Args:
        date_str: Raw date string from portal

    Returns:
        Standardized date string (YYYY-MM-DD) or None if invalid
    """
    if not date_str or not isinstance(date_str, str):
        return None

    date_str = date_str.strip()
    if not date_str:
        return None

    # Already in standard format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # Common formats to try
    formats = [
        # UK formats
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        # Named months (short)
        "%d %b %Y",
        "%d-%b-%Y",
        "%d %b, %Y",
        # Named months (full)
        "%d %B %Y",
        "%d-%B-%Y",
        "%d %B, %Y",
        # ISO with time
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        # US format (less common but seen)
        "%m/%d/%Y",
    ]

    # Try each format
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try to extract date with regex
    # DD/MM/YYYY or DD-MM-YYYY
    match = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})", date_str)
    if match:
        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # YYYY-MM-DD
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
    if match:
        year, month, day = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def parse_date_to_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse a date string to a datetime object.

    Args:
        date_str: Raw date string

    Returns:
        datetime object or None if invalid
    """
    standardized = standardize_date(date_str)
    if standardized:
        return datetime.strptime(standardized, "%Y-%m-%d")
    return None


def format_date_for_idox(date: datetime) -> str:
    """
    Format a date for IDOX portal search forms.

    IDOX uses DD/MM/YYYY format.

    Args:
        date: datetime object

    Returns:
        Formatted date string
    """
    return date.strftime("%d/%m/%Y")


def format_date_for_agile(date: datetime) -> str:
    """
    Format a date for Agile API requests.

    Agile uses YYYY-MM-DD format.

    Args:
        date: datetime object

    Returns:
        Formatted date string
    """
    return date.strftime("%Y-%m-%d")
