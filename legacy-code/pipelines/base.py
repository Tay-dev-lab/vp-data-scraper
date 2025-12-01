from itemadapter import ItemAdapter
import logging
from typing import Dict, List, Any
import json
from pathlib import Path

class BasePipeline:
    """Base pipeline with common functionality"""
    
    def __init__(self, settings=None):
        self.settings = settings or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stats = {}
        
    @classmethod
    def from_crawler(cls, crawler):
        return cls(settings=crawler.settings)
    
    def open_spider(self, spider):
        self.spider = spider
        
    def close_spider(self, spider):
        # Log stats when spider closes
        for stat, value in self.stats.items():
            spider.crawler.stats.set_value(f"{self.__class__.__name__}/{stat}", value)
    
    def update_stats(self, key, value=1, increment=False):
        if increment:
            self.stats[key] = self.stats.get(key, 0) + value
        else:
            self.stats[key] = value 