"""
Atlas Spider module for RBKC (Royal Borough of Kensington and Chelsea).

Atlas is a custom SolidStart-based planning portal used by RBKC.
It wraps an Idox Uniform backend with a modern SPA frontend.
"""

from .atlas_spider import AtlasSpider

__all__ = ["AtlasSpider"]
