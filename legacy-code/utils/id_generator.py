"""
ID Generator module using nanoid for short unique IDs.

This module provides utility functions for generating shorter IDs than UUIDs.
"""
import uuid
from nanoid import generate

def generate_short_id(size=16):
    """
    Generate a short unique ID using nanoid.
    
    Args:
        size (int): The length of the generated ID. Default is 16.
        
    Returns:
        str: A unique ID with the specified length.
    """
    return generate(size=size)

def generate_uuid():
    """
    Generate a standard UUID.
    
    Returns:
        str: A standard UUID string.
    """
    return str(uuid.uuid4())