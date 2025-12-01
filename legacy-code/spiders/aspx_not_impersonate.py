from .aspx_spider import AspxSpider, ASPX_SEARCH_URLS
import scrapy

class AspxNotImpersonate(AspxSpider):
    name = "aspx_not_impersonate"
    
    settings = {
        # Use standard Scrapy download handlers
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler",
            "https": "scrapy.core.downloader.handlers.http.HTTPDownloadHandler"
        },
        # SSL settings
        'DOWNLOADER_CLIENTCONTEXTFACTORY': 'scrapy.core.downloader.contextfactory.BrowserLikeContextFactory',
        'DOWNLOAD_TIMEOUT': 60,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429, 60],
        'DOWNLOAD_DELAY': 5,
        'CONCURRENT_REQUESTS': 1
    }

    def start_requests(self):
        for url in ASPX_SEARCH_URLS:
            yield scrapy.Request(
                url=url,
                callback=self.search_form,
                meta={
                    "download_timeout": self.settings['DOWNLOAD_TIMEOUT'],
                    "handle_httpstatus_list": [500, 502, 503, 504, 408, 429, 60],
                    "verify": False  # Disable SSL verification
                }
            ) 