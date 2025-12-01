"""
ID generation utilities.
"""

import uuid
import string
import random


def generate_uuid() -> str:
    """
    Generate a standard UUID v4.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def generate_short_id(size: int = 12) -> str:
    """
    Generate a short random ID using alphanumeric characters.

    Args:
        size: Length of the ID (default 12)

    Returns:
        Random alphanumeric string
    """
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=size))


def generate_document_id(council: str, app_ref: str, filename: str) -> str:
    """
    Generate a deterministic document ID from its components.

    This allows deduplication - same inputs always produce same ID.

    Args:
        council: Council name
        app_ref: Application reference
        filename: Document filename

    Returns:
        Short hash ID
    """
    import hashlib

    combined = f"{council}:{app_ref}:{filename}".lower()
    hash_bytes = hashlib.sha256(combined.encode()).digest()
    return hash_bytes[:8].hex()
