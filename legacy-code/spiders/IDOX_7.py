import scrapy
from spiders.idox_spider import IdoxSpider
from urls.portal_websites import IDOX_7

class IDOX7Spider(IdoxSpider):
    name = "IDOX_7"
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override the URL list with IDOX_7
        self.start_urls = IDOX_7
        # Update allowed domains based on the new URL list
        self.allowed_domains = [url.split('/')[2] for url in IDOX_7]
    
    def start_requests(self):
        """Generate initial requests for each council in IDOX_7"""
        for url in self.start_urls:
            council_name = self.extract_council_name(url)
            self.logger.info(f"Starting scrape for council: {council_name}")
            
            yield scrapy.Request(
                url=url,
                callback=self.parse_search_form,
                cb_kwargs={'council_name': council_name},
                dont_filter=True
            ) 