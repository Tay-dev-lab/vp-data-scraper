import asyncio
import logging
from datetime import datetime, timedelta
from rich.logging import RichHandler
from selenium_driverless import webdriver
import sys
import os
from bs4 import BeautifulSoup
import scrapy
from scrapy import Request, FormRequest
from scrapy.crawler import CrawlerProcess
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose, TakeFirst
import os
from urllib.parse import urlparse

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from urls.portal_websites import ASPX_SEARCH_URLS

# Setup logging
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("rich")

def get_domain(url):
    """Extract domain from URL using urllib.parse"""
    parsed = urlparse(url)
    domain = parsed.netloc
    # Remove port number if present
    if ':' in domain:
        domain = domain.split(':')[0]
    return domain

class ViewstateManager:
    def __init__(self) -> None:
        self.vs_token = None
        self.tokens = {}
        self.cookies = {}  # Store cookies for each domain

    async def get_token(self, url):
        try:
            domain = get_domain(url)
            log.debug(f"Processing URL: {url} for domain: {domain}")
            
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            async with webdriver.Chrome(options=options) as driver:
                await asyncio.sleep(1)
                await driver.get(url)
                await asyncio.sleep(2)
                
                # Get cookies
                cookies = await driver.get_cookies()
                self.cookies[domain] = cookies
                log.info(f"Retrieved {len(cookies)} cookies for {domain}")
                
                # Get the page source
                page_source = await driver.page_source
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Look for __VIEWSTATE in the form
                viewstate = soup.find('input', {'name': '__VIEWSTATE'})
                if viewstate:
                    vs_token = viewstate.get('value')
                    self.tokens[domain] = vs_token
                    log.info(f"Successfully retrieved __VIEWSTATE token for {domain}")
                    return vs_token, cookies
                else:
                    log.warning(f"No __VIEWSTATE found in form for {domain}")
                    # Log the HTML for debugging
                    log.debug(f"Page source: {page_source[:500]}...")  # First 500 chars
                    return None, cookies
                    
        except Exception as e:
            log.error(f"Error getting __VIEWSTATE token for {url}: {e}")
            return None, None

class AspxSel(scrapy.Spider):
    name = 'aspx_sel_spider'
    allowed_domains = []  # Will be populated dynamically
    start_urls = ASPX_SEARCH_URLS  # Use the imported URLs
    
    # Date variables for search
    date_from = '15-02-2025'
    date_to = '21-02-2025'

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 5,  # Increased delay between requests
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'RETRY_DELAY': 5,  # Delay between retries
        'FEEDS': {
            'aspx_search_results.json': {
                'format': 'json',
                'overwrite': True
            }
        },
        'DOWNLOAD_TIMEOUT': 60,  # Reduced from 180 to 60 seconds
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
        'HTTPERROR_ALLOWED_CODES': [403, 404, 500, 502, 503, 504],
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
        },
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def __init__(self, date_from=None, date_to=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vs_manager = ViewstateManager()
        # Populate allowed_domains from start_urls using proper domain extraction
        self.allowed_domains = [get_domain(url) for url in self.start_urls]
        
        # Allow date override from command line
        if date_from:
            self.date_from = date_from
        if date_to:
            self.date_to = date_to

    def start_requests(self):
        # Process each URL in the list
        for url in self.start_urls:
            domain = get_domain(url)
            yield Request(
                url=url,
                callback=self.handle_initial_page,
                dont_filter=True,
                meta={'first_request': True, 'base_url': url, 'domain': domain}
            )

    async def handle_initial_page(self, response):
        base_url = response.meta.get('base_url')
        domain = response.meta.get('domain', get_domain(base_url))
        
        if response.meta.get('first_request'):
            # Get the viewstate token and cookies
            vs_token, cookies = await self.vs_manager.get_token(base_url)
            if not vs_token:
                self.logger.error(f"Could not get viewstate for {base_url}")
                return
            
            # Convert cookies to dict format for Scrapy
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies} if cookies else {}
            
            # Create form request with the viewstate token and cookies
            yield FormRequest.from_response(
                response,
                formdata={
                    "__VIEWSTATE": vs_token,
                    'dateStart': self.date_from, 
                    'dateEnd': self.date_to, 
                    'cboSelectDateValue': 'DATE_DECISION',
                    'csbtnSearch': 'Search',
                    'rbGroup': 'rbRange'
                },
                cookies=cookie_dict,
                callback=self.parse_results,
                meta={'base_url': base_url, 'domain': domain}
            )

    def parse_results(self, response):
        # Log the response for debugging
        self.logger.info(f"Response from {response.meta.get('base_url')}:")
        self.logger.info(f"Status: {response.status}")
        
        if response.status in [403, 404, 500, 502, 503, 504]:
            self.logger.error(f"Received error status {response.status} for {response.url}")
            return

        links = response.xpath('//a[@class="data_text"]/@href').getall()
        for link in links:
            # Convert relative URLs to absolute URLs
            absolute_url = response.urljoin(link)
            yield scrapy.Request(
                url=absolute_url,
                callback=self.parse_plan_apps,
                meta={
                    "impersonate": "chrome120",
                    "dont_retry": False,
                    "handle_httpstatus_list": [403, 404, 500, 502, 503, 504],
                    "download_timeout": 30,
                    "max_retry_times": 3,
                    "retry_priority_adjust": -1,
                },
                cb_kwargs={"absolute_url": absolute_url},
                errback=self.handle_error
            )

    def handle_error(self, failure):
        """Handle request failures"""
        request = failure.request
        self.logger.error(f"Request failed: {request.url}")
        self.logger.error(f"Error: {failure.value}")
        
        # Log additional details if available
        if hasattr(failure.value, 'response'):
            self.logger.error(f"Response status: {failure.value.response.status}")
            self.logger.error(f"Response headers: {failure.value.response.headers}")
        
        # Handle specific error types
        if isinstance(failure.value, TimeoutError):
            self.logger.warning(f"Timeout occurred for {request.url}, will retry with increased delay")
            # Add your timeout handling logic here
        elif '403' in str(failure.value):
            self.logger.warning(f"Access forbidden for {request.url}, might need to adjust headers or wait")
            # Add your 403 handling logic here
        elif '429' in str(failure.value):
            self.logger.warning("Rate limit detected, waiting before retry...")
            # Add your rate limit handling logic here

    def parse_plan_apps(self, response, absolute_url):
        loader = ItemLoader(item=PlanningApplicationItem(), response=response)
        
        try:
            # Base XPaths with improved section detection
            details_base = '//div[contains(@class,"dataview")][.//h1[contains(., "Application Details")]]'
            progress_base = '//div[contains(@class,"dataview")][.//h1[contains(., "Application Progress Summary")]]'

            # Generic field extraction with error handling
            def add_field(field_name, label):
                try:
                    loader.add_xpath(
                        field_name,
                        f'{details_base}//div[.//span[contains(., "{label}")]]/text()',
                        MapCompose(str.strip, lambda x: x if x else None)
                    )
                except KeyError as e:
                    self.logger.warning(f"Missing field {field_name} in {response.url}")
                except Exception as e:
                    self.logger.error(f"Error extracting {field_name} from {response.url}: {str(e)}")

            # Application Details Section
            try:
                add_field('council_name', self.allowed_domains)
                add_field('council_url', absolute_url)
                add_field('application_reference', 'Application Number')
                add_field('site_address', 'Site Address')
                add_field('application_type', 'Application Type')
                add_field('description', 'Proposal')
                add_field('status', 'Current Status')
                add_field('applicant_name', 'Applicant')
                add_field('agent_name', 'Agent')
                add_field('ward', 'Wards')
                add_field('parish', 'Parishes')
                add_field('case_officer_name', 'Planning Officer')
                add_field('case_officer_telephone', 'Case Officer / Tel')
                add_field('determination_level', 'Determination Level')
                add_field('development_type', 'Development Type')
                add_field('location_coordinates', 'Location Co ordinates')
                add_field('os_mapsheet', 'OS Mapsheet')
                add_field('appeal_submitted', 'Appeal Submitted?')
                add_field('appeal_decision', 'Appeal Decision')
                add_field('division', 'Division')
                add_field('existing_land_use', 'Existing Land Use')
                add_field('proposed_land_use', 'Proposed Land Use')
            except Exception as e:
                self.logger.error(f"Error in main field processing for {response.url}: {str(e)}")

            # Add URL
            loader.add_value('application_url', absolute_url)
        
            # Application Progress Section
            try:
                loader.add_xpath(
                    'application_registered_date',
                    f'{progress_base}//div[.//span[contains(., "Application Registered")]]/text()',
                    MapCompose(str.strip)
                )
                loader.add_xpath(
                    'comments_until_date',
                    f'{progress_base}//div[.//span[contains(., "Comments Until")]]/text()',
                    MapCompose(str.strip)
                )
            except Exception as e:
                self.logger.error(f"Error processing progress section for {response.url}: {str(e)}")

       

        except KeyError as e:
            self.logger.warning(f"Missing key {str(e)} in {response.url}")
            return
        except Exception as e:
            self.logger.error(f"Critical error processing {response.url}: {str(e)}")
            return

        try:
            return loader.load_item()
        except Exception as e:
            self.logger.error(f"Failed to load item for {response.url}: {str(e)}")
            return
