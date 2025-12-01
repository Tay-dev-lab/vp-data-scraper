"""
Text cleaning utilities for normalizing scraped data.
"""

import re
from typing import Optional


def clean_text(text: Optional[str]) -> Optional[str]:
    """
    Clean and normalize text from scraped HTML.

    - Removes HTML tags
    - Normalizes whitespace
    - Strips leading/trailing whitespace
    - Returns None for empty strings

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text or None if empty
    """
    if text is None:
        return None

    if not isinstance(text, str):
        text = str(text)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Strip
    text = text.strip()

    # Return None for empty strings
    return text if text else None


def clean_filename(filename: Optional[str]) -> Optional[str]:
    """
    Clean a filename for storage.

    - Removes path components
    - Removes problematic characters
    - Normalizes whitespace

    Args:
        filename: Original filename

    Returns:
        Cleaned filename or None if empty
    """
    if not filename:
        return None

    # Get just the filename (remove path)
    filename = filename.split("/")[-1].split("\\")[-1]

    # Remove query strings
    filename = filename.split("?")[0]

    # Replace problematic characters with underscore
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Normalize whitespace
    filename = re.sub(r"\s+", "_", filename)

    # Remove multiple underscores
    filename = re.sub(r"_+", "_", filename)

    # Strip underscores from ends
    filename = filename.strip("_")

    return filename if filename else None


def extract_postcode(text: Optional[str]) -> Optional[str]:
    """
    Extract a UK postcode from text.

    Args:
        text: Text that may contain a postcode

    Returns:
        Extracted postcode or None if not found
    """
    if not text:
        return None

    # UK postcode regex (simplified)
    pattern = r"\b([A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2})\b"
    match = re.search(pattern, text.upper())

    if match:
        postcode = match.group(1)
        # Normalize spacing
        if " " not in postcode:
            # Insert space before the last 3 characters
            postcode = postcode[:-3] + " " + postcode[-3:]
        return postcode.upper()

    return None
