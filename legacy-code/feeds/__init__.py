"""
Feed export helpers for Scrapy.
"""
from typing import Dict, Any, Optional


class PlanningAppItemFilter:
    """
    Custom item filter that accepts both Scrapy Items and dictionaries
    that match a planning application data structure.
    
    This follows Scrapy's ItemFilter interface.
    """
    def __init__(self, feed_options: Optional[Dict[str, Any]] = None):
        self.feed_options = feed_options or {}
    
    def accepts(self, item: Any) -> bool:
        """
        Return True if item should be exported to the planning app feed.
        
        Parameters:
            item: A Scrapy item or dictionary
            
        Returns:
            bool: True if the item should be exported
        """
        # Check if it has key fields of a planning application
        required_fields = ['site_address', 'proposal']
        optional_fields = ['application_reference', 'council_name', 'status', 'decision']
        
        # Check if it has required fields
        has_required = all(field in item for field in required_fields)
        
        # Check if it has at least one optional field
        has_optional = any(field in item for field in optional_fields)
        
        # It's a planning application if it has required fields and at least one optional field
        return has_required and has_optional


# Backward compatibility for simple string function reference
def is_planning_application_item(item: Dict[str, Any]) -> bool:
    """
    A simple function version of the filter.
    
    This is kept for backward compatibility with string references.
    """
    filter_instance = PlanningAppItemFilter()
    return filter_instance.accepts(item)