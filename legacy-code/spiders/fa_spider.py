import asyncio
import logging
from datetime import datetime, timedelta
from rich.logging import RichHandler
import scrapy
from scrapy import Request, FormRequest
from selenium_driverless import webdriver
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
from urls.portal_websites import FA_SEARCH_URLS  # Import the URLs list

# Setup logging
FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=RichHandler()
)
log = logging.getLogger("rich")

class WafTokenManager:
    def __init__(self):
        self.waf_token = None
        self.tokens = {}  # Store tokens for each domain
        
    async def get_token(self, url):
        """Get a fresh WAF token using selenium-driverless"""
        try:
            domain = url.split('/')[2]  # Extract domain from URL
            
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            async with webdriver.Chrome(options=options) as driver:
                await asyncio.sleep(1)
                await driver.get(url)
                await asyncio.sleep(5)
                
                cookies = await driver.get_cookies()
                waf_token = next((c['value'] for c in cookies if 'waf' in c['name'].lower()), None)
                
                if waf_token:
                    self.tokens[domain] = waf_token
                    return waf_token
                    
        except Exception as e:
            log.error(f"Error getting WAF token for {url}: {e}")
            return None

class FaSpider(scrapy.Spider):
    name = 'fa_spider'
    allowed_domains = []  # Will be populated dynamically
    start_urls = FA_SEARCH_URLS  # Use the imported URLs
    
    # Date variables for search
    date_from = '01-01-2025'
    date_to = '15-04-2025'

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        
        # Add Download Handlers for TLS fingerprint masking
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_impersonate.ImpersonateDownloadHandler",
            "https": "scrapy_impersonate.ImpersonateDownloadHandler",
        },
        
        # Retry settings
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 400, 403, 404, 408, 406],
        'RETRY_PRIORITY_ADJUST': -1,
        
        # Request timeouts
        'DOWNLOAD_TIMEOUT': 180,
        
        # Auto throttle settings
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 5,
        'AUTOTHROTTLE_MAX_DELAY': 60,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        
        # Close spider after certain number of errors
        'CLOSESPIDER_ERRORCOUNT': 10,
        'CLOSESPIDER_TIMEOUT': 7200,
        
        # Handle HTTP error codes
        'HTTPERROR_ALLOWED_CODES': [406],
        'HTTPERROR_ALLOW_ALL': False,
        
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.CustomProxyMiddleware': 750,
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': 550,
            # Add any other middleware you need here
        },
        
        'FEEDS': {
            'fa_search_results.json': {
                'format': 'json',
                'overwrite': False
            }
        }
    }

    def __init__(self, date_from=None, date_to=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.waf_manager = WafTokenManager()
        # Populate allowed_domains from start_urls
        self.allowed_domains = [url.split('/')[2] for url in self.start_urls]
        
        # Allow date override from command line
        if date_from:
            self.date_from = date_from
        if date_to:
            self.date_to = date_to

    def start_requests(self):
        # Process each URL in the list
        for url in self.start_urls:
            yield Request(
                url=url,
                callback=self.handle_initial_page,
                dont_filter=True,
                meta={'first_request': True, 'base_url': url}
            )

    async def handle_initial_page(self, response):
        base_url = response.meta.get('base_url')
        domain = base_url.split('/')[2]
        
        if response.meta.get('first_request'):
            token = await self.waf_manager.get_token(base_url)
            if not token:
                self.logger.error(f"Could not get WAF token for {base_url}")
                return

            # Using exact parameters from shell output
            yield FormRequest(
                url=base_url,
                formdata={
                    'fa': 'search',
                    'submitted': 'true',
                    'decision_issued_date_from': self.date_from,
                    'decision_issued_date_to': self.date_to
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
                    'Accept': '*/*',
                    'Accept-Language': 'en-GB,en;q=0.5',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': f'https://{domain}',
                    'Connection': 'keep-alive',
                    'Referer': base_url,
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                },
                cookies={
                    'aws-waf-token': token,
                    'userlanguage': 'en'
                },
                callback=self.parse_results,
                meta={
                    'waf_token': token, 
                    'page': 1,
                    'base_url': base_url,
                    'domain': domain
                },
                dont_filter=True
            )

    def parse_results(self, response):
        # Extract application IDs
        application_ids = response.css('button.view_application::attr(data-id)').getall()
        base_url = response.meta.get('base_url')
        domain = response.meta.get('domain')
        
        for application_id in application_ids:
            yield self.make_detail_request(application_id, response, base_url)

        # If we found applications, request next page
        if application_ids:
            current_page = response.meta.get('page', 1)
            next_page = current_page + 1
            
            yield FormRequest(
                url=base_url,
                formdata={
                    'fa': 'search',
                    'page': str(next_page),
                    'ajax': 'true',
                    'result_loader': 'true',
                    'submitted': 'true',
                    'decision_issued_date_from': self.date_from,
                    'decision_issued_date_to': self.date_to
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
                    'Accept': '*/*',
                    'Accept-Language': 'en-GB,en;q=0.5',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Origin': f'https://{domain}',
                    'Connection': 'keep-alive',
                    'Referer': base_url,
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin',
                },
                callback=self.parse_results,
                meta={
                    'waf_token': response.meta['waf_token'],
                    'page': next_page,
                    'base_url': base_url,
                    'domain': domain
                },
                dont_filter=True
            )

    def make_detail_request(self, application_id, response, base_url):
        """Helper method to create detail page requests"""
        return FormRequest(
            url=base_url,
            formdata={
                'fa': 'getApplication',
                'id': application_id
            },
            callback=self.parse_application,
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': response.url,
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            meta={
                'waf_token': response.meta['waf_token'],
                'application_id': application_id,
                'base_url': base_url,
                'domain': response.meta.get('domain')
            },
            dont_filter=True
        )

    def parse_application(self, response):
        loader = ItemLoader(item=PlanningApplicationItem(), response=response)
        
        # Use application_url instead of source_url
        loader.add_value('application_url', response.meta.get('base_url'))
        
        # Basic application details
        loader.add_xpath('application_reference', 
            "//div[div/strong[contains(text(), 'Application Reference Number')]]/div[2]/text()")
        loader.add_xpath('application_type',
            "//div[div/strong[contains(text(), 'Application Type')]]/div[2]/text()")
        loader.add_xpath('proposal',
            "//div[div/strong[contains(text(), 'Proposal')]]/div[2]/text()")
        
        # Applicant and agent details
        loader.add_xpath('applicant_name',
            "//div[div/strong[contains(text(), 'Applicant')]]/div[2]/text()")
        loader.add_xpath('agent_name',
            "//div[div/strong[contains(text(), 'Agent')]]/div[2]/text()")
        
        # Location details
        loader.add_xpath('site_address',
            "//div[div/strong[contains(text(), 'Location')]]/div[2]/text()")
        loader.add_xpath('ward',
            "//div[div/strong[contains(text(), 'Ward')]]/div[2]/text()")
        loader.add_xpath('parish',
            "//div[div/strong[contains(text(), 'Parish / Community')]]/div[2]/text()")
        
        # Officer and decision details
        loader.add_xpath('case_officer_name',
            "//div[div/strong[contains(text(), 'Officer')]]/div[2]/text()")
        loader.add_xpath('determination_level',
            "//div[div/strong[contains(text(), 'Decision Level')]]/div[2]/text()")
        loader.add_xpath('status',
            "//div[div/strong[contains(text(), 'Application Status')]]/div[2]/text()")
        
        # Date information
        loader.add_xpath('received_date',
            "//div[div/strong[contains(text(), 'Received Date')]]/div[2]/text()")
        loader.add_xpath('valid_from',
            "//div[div/strong[contains(text(), 'Valid Date')]]/div[2]/text()")
        loader.add_xpath('expiry_date',
            "//div[div/strong[contains(text(), 'Expiry Date')]]/div[2]/text()")
        loader.add_xpath('extension_of_time',
            "//div[div/strong[contains(text(), 'Extension Of Time')]]/div[2]/text()")
        loader.add_xpath('extended_target_decision_date',
            "//div[div/strong[contains(text(), 'Extension Of Time Due Date')]]/div[2]/text()")
        
        # Performance agreement details
        loader.add_xpath('planning_performance_agreement',
            "//div[div/strong[contains(text(), 'Planning Performance Agreement')]]/div[2]/text()")
        loader.add_xpath('planning_performance_agreement_due_date',
            "//div[div/strong[contains(text(), 'Planning Performance Agreement Due Date')]]/div[2]/text()")
        
        # Committee dates
        loader.add_xpath('committee_date',
            "//div[div/strong[contains(text(), 'Proposed Committee Date')]]/div[2]/text()")
        loader.add_xpath('actual_committee_date',
            "//div[div/strong[contains(text(), 'Actual Committee Date')]]/div[2]/text()")
        
        # Decision details
        loader.add_xpath('decision_date',
            "//div[div/strong[contains(text(), 'Decision Issued Date')]]/div[2]/text()")
        loader.add_xpath('decision',
            "//div[div/strong[contains(text(), 'Decision:')]]/div[2]/text()")
        
        # Appeal information
        loader.add_xpath('appeal_reference',
            "//div[div/strong[contains(text(), 'Appeal Reference')]]/div[2]/text()")
        loader.add_xpath('appeal_status',
            "//div[div/strong[contains(text(), 'Appeal Status')]]/div[2]/text()")
        loader.add_xpath('appeal_decision',
            "//div[div/strong[contains(text(), 'Appeal External Decision')]]/div[2]/text()")
        loader.add_xpath('appeal_external_decision_date',
            "//div[div/strong[contains(text(), 'Appeal External Decision Date')]]/div[2]/text()")

        return loader.load_item() 