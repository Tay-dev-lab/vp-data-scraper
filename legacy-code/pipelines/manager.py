import logging
from typing import Dict, Any, List
import time

class PipelineManager:
    """
    Manages the flow of data between pipeline stages and provides monitoring
    
    This class is optional but can be useful for debugging and monitoring the pipeline.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'pipeline_start_time': time.time(),
            'items_processed': 0,
            'items_rejected': 0,
            'database_errors': 0,
            'processing_time': 0,
        }
        
    def track_item(self, item, stage, status='success'):
        """Track an item through a pipeline stage"""
        self.stats['items_processed'] = self.stats.get('items_processed', 0) + 1
        
        # Add stage-specific stats
        stage_key = f"{stage}_{status}"
        self.stats[stage_key] = self.stats.get(stage_key, 0) + 1
        
        # Log for debugging
        self.logger.debug(f"Pipeline stage {stage}: {status} for item {item.get('application_id')}")
    
    def log_error(self, stage, error, item=None):
        """Log an error in a pipeline stage"""
        error_key = f"{stage}_errors"
        self.stats[error_key] = self.stats.get(error_key, 0) + 1
        
        self.logger.error(f"Error in {stage}: {error}")
        if item:
            self.logger.debug(f"Problematic item: {item.get('application_id')}")
    
    def get_stats(self):
        """Get current pipeline statistics"""
        # Calculate processing time
        self.stats['processing_time'] = time.time() - self.stats['pipeline_start_time']
        return self.stats 