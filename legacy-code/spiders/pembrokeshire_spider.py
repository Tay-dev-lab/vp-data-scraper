import scrapy
from scrapy.loader import ItemLoader
from items.items import PlanningApplicationItem
from urllib.parse import urlencode
from spiders.agile_spider import AgileSpider

class PembrokeshireSpider(AgileSpider):
    name = "pembrokeshire_spider"
    
    # Override the x-client value for Pembrokeshire
    x_client = "PEMBROKESHIRECOAST"
    
    # Override the parameters if needed
    params = {
        'decisionDateFrom': '2025-02-17',
        'decisionDateTo': '2025-02-19'
    }

    def start_requests(self):
        """
        Override start_requests to use the custom x-client
        """
        # Use the API endpoint from the parent class
        url = f"{self.api_url}?{urlencode(self.params)}"
        
        # Get headers with the fixed x-client for Pembrokeshire
        headers = self.get_headers(self.x_client)
        
        yield scrapy.Request(
            url=url,
            headers=headers,
            callback=self.parse,
            dont_filter=True,
            meta={
                'params': self.params,
                'impersonate': 'chrome120',
                'x_client': self.x_client
            }
        ) 