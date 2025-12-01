from scrapy import signals
from scrapy.exceptions import NotConfigured
from collections import defaultdict
from datetime import datetime
import logging
from urllib.parse import urlparse
import json
import os
import subprocess

# Define a summary item class in base/base/items/items.py
# class URLSummaryItem(scrapy.Item):
#     url = scrapy.Field()
#     count = scrapy.Field()
#     spider_name = scrapy.Field()
#     timestamp = scrapy.Field()

class ItemFeedExporterExtension:
    """
    Extension that captures items early in the pipeline process and sends them
    directly to the feed exporter before they are modified by the validation pipeline.
    """

    def __init__(self, feed_uri=None, feed_format=None):
        self.logger = logging.getLogger(__name__)
        
    @classmethod
    def from_crawler(cls, crawler):
        # Get settings
        ext = cls()
        
        # Connect to the item scraped signal
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        
        return ext
    
    def item_scraped(self, item, response, spider):
        """
        When an item is scraped, check if it's a PlanningApplicationItem
        and if so, make a copy and pass it directly to the feed exporter signal.
        """
        # Skip items that have the feed_direct flag to avoid infinite recursion
        if hasattr(response, 'meta') and response.meta.get('feed_direct'):
            return
            
        # Only process if the item is a PlanningApplicationItem
        from items.items import PlanningApplicationItem
        
        if isinstance(item, PlanningApplicationItem):
            # Log what we're doing
            spider.logger.debug(f"ItemFeedExporterExtension: Captured PlanningApplicationItem {item.get('application_reference', 'unknown')}")
            
            # Create a clone of the item
            # Note: This is already a Scrapy Item, so we don't need to convert it
            item_copy = item.copy()
            
            # Add a marker field to indicate this is an original item (for debugging)
            item_copy['_original_item'] = True
            
            # Create a response copy with the feed_direct flag set
            from scrapy.http import Response
            response_copy = Response(response.url, headers=response.headers)
            response_copy.meta['feed_direct'] = True
            
            # Send the item to the feed exporter
            spider.crawler.signals.send_catch_log(
                signal=signals.item_scraped,
                item=item_copy,
                spider=spider,
                response=response_copy
            )

class LogFileExtension:
    """Extension to set up log file with spider name and timestamp"""
    
    @classmethod
    def from_crawler(cls, crawler):
        # Create the extension
        ext = cls()
        
        # Connect to the spider_opened signal
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        
        return ext
    
    def spider_opened(self, spider):
        """Set up log file when spider opens"""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Generate log filename with spider name and timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"logs/{spider.name}_log_{timestamp}.log"
        
        # Configure logging to file
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        ))
        
        # Get the root logger and add our file handler
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        # Log that we've set up the log file
        spider.logger.info(f"Logging to file: {log_filename}")

class PlanningStatsSummaryExtension:
    """Extension to track planning applications and HTTP status codes per domain"""
    
    def __init__(self):
        self.domain_counts = defaultdict(int)
        self.domain_refs = defaultdict(set)  # Track unique reference numbers per domain
        self.domain_status_codes = defaultdict(lambda: defaultdict(int))  # Track status codes per domain
        self.logger = logging.getLogger(__name__)
        
    @classmethod
    def from_crawler(cls, crawler):
        # Instantiate the extension
        ext = cls()
        
        # Connect to the item scraped signal
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        
        # Connect to the response received signal to track status codes
        crawler.signals.connect(ext.response_received, signal=signals.response_received)
        
        # Connect to the spider closed signal to generate the summary
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        
        return ext
    
    def response_received(self, response, request, spider):
        """Track HTTP status codes per domain"""
        # Extract the domain from the URL
        url = response.url
        domain = urlparse(url).netloc
        
        # For some spiders, the council name might be in meta
        council_name = None
        if 'council_name' in request.meta:
            council_name = request.meta['council_name']
            
        # Use council name as the key if available, otherwise use domain
        key = council_name or domain
        
        # Track the status code
        status_code = response.status
        self.domain_status_codes[key][status_code] += 1
        
        # Log the status code
        spider.logger.debug(f"Response {status_code} from {key} ({url})")
        
    def item_scraped(self, item, response, spider):
        """Track each scraped planning application by domain"""
        # Log the item type for debugging
        item_type = type(item).__name__
        spider.logger.info(f"Scraped item type: {item_type}")
        spider.logger.info(f"Item fields: {item.keys() if hasattr(item, 'keys') else 'No keys method'}")
        
        # Skip summary items to avoid recursion
        if hasattr(item, '__class__') and item.__class__.__name__ == 'DomainSummaryItem':
            return
            
        # Extract the domain from the URL
        url = response.url
        domain = urlparse(url).netloc
        
        # For some spiders, the council name might be in meta or in the item
        council_name = None
        if hasattr(item, 'get'):
            # Try to get council name from the item
            council_name = item.get('council_name')
        
        if not council_name and 'council_name' in response.meta:
            council_name = response.meta['council_name']
            
        # Use council name as the key if available, otherwise use domain
        key = council_name or domain
        
        # Check if this item has a planning reference number
        ref_number = None
        if hasattr(item, 'get'):
            # Try different possible field names for planning reference
            for field in ['application_reference', 'reference', 'ref', 'planning_ref']:
                if field in item and item[field]:
                    ref_number = item[field]
                    break
        
        if ref_number:
            # Add this reference to the set for this domain
            self.domain_refs[key].add(ref_number)
            
            # Increment the count for this domain
            self.domain_counts[key] += 1
            
            # Log the scraped item
            spider.logger.info(f"Scraped planning application {ref_number} from {key}")
    
    def spider_closed(self, spider):
        """Generate summary items when the spider finishes"""
        self.logger.info(f"Generating domain summary for {spider.name}")
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create a directory for the reports if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        # Generate a summary file name with spider name and timestamp
        filename = f"reports/planning_summary_{spider.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Group status codes into categories
        domain_status_categories = {}
        for domain, status_counts in self.domain_status_codes.items():
            domain_status_categories[domain] = {
                '2xx_success': sum(count for status, count in status_counts.items() if 200 <= status < 300),
                '4xx_client_errors': sum(count for status, count in status_counts.items() if 400 <= status < 500),
                '5xx_server_errors': sum(count for status, count in status_counts.items() if 500 <= status < 600),
                'specific_codes': {
                    str(status): count for status, count in status_counts.items()
                }
            }
        
        # Create summary data
        summary = {
            'spider_name': spider.name,
            'timestamp': timestamp,
            'total_planning_apps': sum(self.domain_counts.values()),
            'domains_scraped': len(self.domain_counts),
            'domain_stats': [
                {
                    'domain': domain,
                    'planning_apps_count': count,
                    'unique_refs_count': len(self.domain_refs[domain]),
                    # Status code statistics
                    'status_codes': domain_status_categories.get(domain, {
                        '2xx_success': 0,
                        '4xx_client_errors': 0,
                        '5xx_server_errors': 0,
                        'specific_codes': {}
                    }),
                    # Optionally include sample references (limit to 5 to keep the file size reasonable)
                    'sample_refs': list(self.domain_refs[domain])[:5] if self.domain_refs[domain] else []
                } for domain, count in sorted(self.domain_counts.items(), key=lambda x: x[1], reverse=True)
            ]
        }
        
        # Write the summary to a JSON file
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=4)
            
        self.logger.info(f"Planning application summary saved to {filename}")
        
        # Log some basic stats
        self.logger.info(f"Total planning applications scraped: {summary['total_planning_apps']}")
        self.logger.info(f"Domains scraped: {summary['domains_scraped']}")
        
        # Create a summary item for the feed exporter
        from items.items import DomainSummaryItem  # Updated import path
        
        summary_item = DomainSummaryItem(
            spider_name=spider.name,
            timestamp=timestamp,
            total_planning_apps=summary['total_planning_apps'],
            domains_scraped=summary['domains_scraped'],
            domain_stats=summary['domain_stats']
        )
        
        # The item will be automatically exported by the feed exporter
        return summary_item 

class StatusCodeAnalyzerExtension:
    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext
    
    def spider_closed(self, spider):
        """Run the status code analyzer when a spider finishes"""
        spider.logger.info("Running status code analyzer...")
        
        # Get the path to the analyzer script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        analyzer_path = os.path.join(script_dir, 'utils', 'status_code_analizer.py')
        
        # Run the analyzer script
        try:
            result = subprocess.run(
                ['python', analyzer_path, '--latest', '--force'],
                capture_output=True,
                text=True
            )
            spider.logger.info(f"Status code analyzer output: {result.stdout}")
            if result.stderr:
                spider.logger.error(f"Status code analyzer error: {result.stderr}")
        except Exception as e:
            spider.logger.error(f"Failed to run status code analyzer: {e}") 