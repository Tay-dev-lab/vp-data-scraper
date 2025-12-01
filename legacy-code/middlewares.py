# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals

# useful for handling different item types with a single interface
from itemadapter import is_item, ItemAdapter
import dotenv
import os
from urllib.parse import urlparse
import time
from rich.logging import RichHandler
from rich.console import Console
from rich import print as rprint
import logging
import base64

# Configure rich logging
console = Console()
rich_handler = RichHandler(rich_tracebacks=True, markup=True)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[rich_handler]
)

# Get logger for this module
logger = logging.getLogger('middlewares')

dotenv.load_dotenv()

class BaseSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn't have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        console.log(f"[bold blue]Spider opened:[/bold blue] [cyan]{spider.name}[/cyan]")


class BaseDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        console.log(f"[bold blue]Downloader middleware initialized for spider:[/bold blue] [cyan]{spider.name}[/cyan]")


class CustomProxyMiddleware:
    """Middleware to add proxy to requests."""
    
    def __init__(self, proxy=None):
        self.proxy = proxy
        
        if proxy:
            # The proxy URL is already correctly formatted in the .env file
            # We just need to extract the authentication part for headers
            if '@' in proxy:
                # Remove http:// if present
                clean_proxy = proxy.replace('http://', '')
                auth_part = clean_proxy.split('@')[0]
                # Create the auth header
                self.auth = base64.b64encode(auth_part.encode()).decode()
                logger.info(f"Proxy middleware initialized with authentication")
            else:
                self.auth = None
                logger.info(f"Proxy middleware initialized without authentication")
        else:
            self.proxy = None
            self.auth = None
            logger.warning("No proxy configured")
    
    @classmethod
    def from_crawler(cls, crawler):
        proxy = os.getenv("proxy", None)
        return cls(proxy)
    
    def process_request(self, request, spider):
        if not self.proxy:
            return
        
        # Use the complete proxy URL from environment
        request.meta['proxy'] = self.proxy
        
        # For debugging
        spider.logger.debug(f"Added proxy to request for {request.url}")
        
        # Add the Proxy-Authorization header for authenticated proxies
        if self.auth:
            request.headers['Proxy-Authorization'] = f'Basic {self.auth}'


# class DynamicDomainMiddleware:
#     def process_spider_output(self, response, result, spider):
#         # Extract current response domain
#         current_domain = urlparse(response.url).hostname

#         # Add to allowed domains if new
#         if current_domain and current_domain not in spider.allowed_domains:
#             spider.allowed_domains.append(current_domain)
#             spider.logger.debug(f"Added new allowed domain: {current_domain}")

#         return result


# class ArcusSpiderMiddleware:
#     @classmethod
#     def from_crawler(cls, crawler):
#         s = cls()
#         crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
#         return s

#     def process_request(self, request, spider):
#         request.headers['X-Requested-With'] = 'XMLHttpRequest'
#         return None

#     def spider_opened(self, spider):
#         spider.logger.info('Spider opened: %s' % spider.name)


import time
from scrapy import signals

class Handle202Middleware:
    def process_response(self, request, response, spider):
        if response.status == 202:
            retries = request.meta.get('retry_times', 0)
            if retries < 3:  # Limit retries
                delay = 5 * (retries + 1)  # Exponential backoff
                console.log(f"[bold yellow]Got 202 response, retry {retries + 1}, waiting {delay}s[/bold yellow]")
                time.sleep(delay)
                request.dont_filter = True
                request.meta['retry_times'] = retries + 1
                return request
            else:
                console.log(f"[bold red]Max retries reached for[/bold red] [cyan]{request.url}[/cyan]")
        return response

class CouncilNameMiddleware:
    """Middleware to ensure council_name is in request meta"""
    
    def process_request(self, request, spider):
        if 'council_name' not in request.meta and hasattr(spider, 'current_council'):
            request.meta['council_name'] = spider.current_council
            console.log(f"[dim]Added council name[/dim] [cyan]{spider.current_council}[/cyan] [dim]to request meta[/dim]")
        return None