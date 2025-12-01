# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import logging


class BasePipeline:
    def process_item(self, item, spider):
        return item

class ResultsLoggingPipeline:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.item_count = 0
    
    def process_item(self, item, spider):
        self.item_count += 1
        # Log every 10 items to avoid excessive logging
        if self.item_count % 10 == 0:
            self.logger.info(f"Processed {self.item_count} items so far")
        return item
    
    def close_spider(self, spider):
        self.logger.info(f"Spider {spider.name} processed a total of {self.item_count} items")

class ItemDebugPipeline:
    """Pipeline to debug items being processed"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.item_count = 0
    
    def process_item(self, item, spider):
        self.item_count += 1
        if self.item_count % 10 == 0 or self.item_count == 1:
            self.logger.info(f"Processed {self.item_count} items. Latest item type: {type(item).__name__}")
        return item
    
    def close_spider(self, spider):
        self.logger.info(f"Total items processed: {self.item_count}")
