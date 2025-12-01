import logging
from datetime import datetime
from rich.logging import RichHandler
import scrapy
from scrapy import Request, FormRequest
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
from urls.portal_websites import ASPX_SEARCH_URLS
from http.cookies import SimpleCookie
from urllib.parse import urlparse
import asyncio
from selenium_driverless import webdriver

# Setup logging
FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=RichHandler()
)
log = logging.getLogger("rich")

class AspxDriverlessSpider(scrapy.Spider):
    name = 'aspx_driverless'
    allowed_domains = []  # Will be populated dynamically
    start_urls = ASPX_SEARCH_URLS

    # Default date range
    date_from = '01/01/2025'
    date_to = '30/01/2025'

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 2,
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'FEEDS': {
            'aspx_search_results.json': {
                'format': 'json',
                'overwrite': True
            }
        }
    }

    def __init__(self, date_from=None, date_to=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Generate allowed_domains from start_urls
        self.allowed_domains = list(
            {
                urlparse(url).netloc.split(":")[0]  # Remove port if present
                for url in self.start_urls
            }
        )
        if date_from:
            self.date_from = date_from
        if date_to:
            self.date_to = date_to

    async def get_page_data(self, url):
        """Get page data using selenium-driverless"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            async with webdriver.Chrome(options=options) as driver:
                await asyncio.sleep(1)
                await driver.get(url)
                await asyncio.sleep(2)
                
                # Get cookies
                cookies = await driver.get_cookies()
                cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                
                # Get page source for form data
                page_source = await driver.get_page_source()
                
                # Get headers
                headers = await driver.get_headers()
                
                return {
                    'cookies': cookies_dict,
                    'page_source': page_source,
                    'headers': headers
                }
                
        except Exception as e:
            log.error(f"Error getting page data for {url}: {e}")
            return None

    def start_requests(self):
        for url in self.start_urls:
            domain = urlparse(url).netloc
            yield Request(
                url=url,
                callback=self.handle_initial_page,
                dont_filter=True,
                meta={
                    'first_request': True, 
                    'base_url': url,
                    'domain': domain
                }
            )

    async def handle_initial_page(self, response):
        domain = response.meta.get('domain')
        base_url = response.meta.get('base_url')
        
        # Get page data using selenium-driverless
        page_data = await self.get_page_data(base_url)
        if not page_data:
            self.logger.error(f"Could not get page data from {domain}")
            return

        # Extract viewstate and eventvalidation from the page source
        viewstate = response.css('input#__VIEWSTATE::attr(value)').get()
        viewstategenerator = response.css('input#__VIEWSTATEGENERATOR::attr(value)').get()
        eventvalidation = response.css('input#__EVENTVALIDATION::attr(value)').get()

        if not all([viewstate, viewstategenerator, eventvalidation]):
            self.logger.error(f"Could not extract required form values from {domain}")
            return

        # Define the form data
        formdata = {
            '__VIEWSTATE': viewstate,
            '__VIEWSTATEGENERATOR': viewstategenerator,
            '__EVENTVALIDATION': eventvalidation,
            'txtApplicationNumber': '',
            'txtApplicantName': '',
            'txtAgentName': '',
            'cboStreetReferenceNumber': '',
            'txtProposal': '',
            'cboWardCode': '',
            'cboParishCode': '',
            'cboApplicationTypeCode': '',
            'cboDevelopmentTypeCode': '',
            'cboStatusCode': '',
            'cboSelectDateValue': 'DATE_RECEIVED',
            'cboMonths': '1',
            'cboDays': '1',
            'dateStart': self.date_from,
            'dateEnd': self.date_to,
            'rbGroup': 'rbNotApplicable',
            'edrDateSelection': '',
            'csbtnSearch': 'Search',
        }

        # Use headers from selenium-driverless
        headers = page_data['headers']
        headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': f'https://{domain}',
            'Referer': base_url,
        })

        # Use cookies from selenium-driverless
        cookies = page_data['cookies']

        yield FormRequest(
            url=base_url,
            formdata=formdata,
            headers=headers,
            cookies=cookies,
            callback=self.parse_results,
            meta={
                'viewstate': viewstate,
                'viewstategenerator': viewstategenerator,
                'eventvalidation': eventvalidation,
                'base_url': base_url,
                'domain': domain,
                'page': 1
            },
            dont_filter=True
        )

    def parse_results(self, response):
        domain = response.meta.get('domain')
        
        # Extract application links
        application_links = response.css('a[href*="ApplicationDetails.aspx"]::attr(href)').getall()
        
        for link in application_links:
            yield Request(
                url=response.urljoin(link),
                callback=self.parse_application,
                meta={
                    'viewstate': response.meta.get('viewstate'),
                    'viewstategenerator': response.meta.get('viewstategenerator'),
                    'eventvalidation': response.meta.get('eventvalidation'),
                    'base_url': response.meta.get('base_url'),
                    'domain': domain
                }
            )

        # Handle pagination if needed
        next_page = response.css('a[href*="Page$Next"]::attr(href)').get()
        if next_page:
            current_page = response.meta.get('page', 1)
            yield FormRequest(
                url=response.url,
                formdata={
                    '__VIEWSTATE': response.meta.get('viewstate'),
                    '__VIEWSTATEGENERATOR': response.meta.get('viewstategenerator'),
                    '__EVENTVALIDATION': response.meta.get('eventvalidation'),
                    '__EVENTTARGET': 'ctl00$ContentPlaceHolder1$grdSearchResults$ctl00$ctl03$ctl01$ctl00',
                    '__EVENTARGUMENT': 'Page$Next'
                },
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-GB,en;q=0.5',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': f'https://{domain}',
                    'Connection': 'keep-alive',
                    'Referer': response.url,
                },
                callback=self.parse_results,
                meta={
                    'viewstate': response.meta.get('viewstate'),
                    'viewstategenerator': response.meta.get('viewstategenerator'),
                    'eventvalidation': response.meta.get('eventvalidation'),
                    'base_url': response.meta.get('base_url'),
                    'domain': domain,
                    'page': current_page + 1
                },
                dont_filter=True
            )

    def parse_application(self, response):
        loader = ItemLoader(item=PlanningApplicationItem(), response=response)
        
        # Add application URL
        loader.add_value('application_url', response.url)
        
        # Add detail page fields using appropriate selectors
        loader.add_xpath('application_reference', 
            "//span[contains(@id, 'lblApplicationNumber')]/text()")
        loader.add_xpath('application_type',
            "//span[contains(@id, 'lblApplicationType')]/text()")
        loader.add_xpath('description',
            "//span[contains(@id, 'lblProposal')]/text()")
        loader.add_xpath('applicant_name',
            "//span[contains(@id, 'lblApplicantName')]/text()")
        loader.add_xpath('site_address',
            "//span[contains(@id, 'lblSiteAddress')]/text()")
        loader.add_xpath('ward',
            "//span[contains(@id, 'lblWard')]/text()")
        loader.add_xpath('parish',
            "//span[contains(@id, 'lblParish')]/text()")
        loader.add_xpath('case_officer_name',
            "//span[contains(@id, 'lblCaseOfficer')]/text()")
        loader.add_xpath('determination_level',
            "//span[contains(@id, 'lblDeterminationLevel')]/text()")
        loader.add_xpath('status',
            "//span[contains(@id, 'lblStatus')]/text()")
        loader.add_xpath('received_date',
            "//span[contains(@id, 'lblReceivedDate')]/text()")
        loader.add_xpath('valid_from',
            "//span[contains(@id, 'lblValidDate')]/text()")
        loader.add_xpath('expiry_date',
            "//span[contains(@id, 'lblExpiryDate')]/text()")
        loader.add_xpath('decision_date',
            "//span[contains(@id, 'lblDecisionDate')]/text()")
        loader.add_xpath('decision',
            "//span[contains(@id, 'lblDecision')]/text()")

        return loader.load_item() 