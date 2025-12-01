import scrapy
from spiders.idox_spider_vs import IdoxSpider

class IDOX_Southend_Spider(IdoxSpider):
    name = "IDOX_Southend"
    
    # Add custom settings to slow down requests
    custom_settings = {
        'DOWNLOAD_DELAY': 5.0,  # Increase delay between requests to 5 seconds
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,  # Reduce concurrent requests per domain
        'AUTOTHROTTLE_ENABLED': True,  # Ensure autothrottle is enabled
        'AUTOTHROTTLE_START_DELAY': 5.0,  # Higher initial delay
        'AUTOTHROTTLE_MAX_DELAY': 60.0,  # Allow longer delays if needed
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,  # Target only 1 concurrent request
        'RANDOMIZE_DOWNLOAD_DELAY': True,  # Randomize to appear more human-like
        'COOKIES_ENABLED': True,  # Keep cookies enabled
        'RETRY_TIMES': 2,  # Reduce retry attempts
        'RETRY_DELAY': 10  # Longer delay between retries
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override the URL list with IDOX_10
        self.start_urls = ["https://publicaccess.southend.gov.uk/online-applications/search.do?action=advanced"]
        # Update allowed domains based on the new URL list
        self.allowed_domains = ["publicaccess.southend.gov.uk"]
    
    def start_requests(self):
        """Generate initial requests for each council in IDOX_10"""
        for url in self.start_urls:
            council_name = self.extract_council_name(url)
            self.logger.info(f"Starting scrape for council: {council_name}")
            
            yield scrapy.Request(
                url=url,
                callback=self.parse_search_form,
                cb_kwargs={'council_name': council_name},
                dont_filter=True
            ) 