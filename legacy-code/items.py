# Define here the models for your scraped items
import scrapy

class DomainSummaryItem(scrapy.Item):
    """Item for storing domain statistics summary for planning applications"""
    spider_name = scrapy.Field()
    timestamp = scrapy.Field()
    total_planning_apps = scrapy.Field()
    domains_scraped = scrapy.Field()
    domain_stats = scrapy.Field() 