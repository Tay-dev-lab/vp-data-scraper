import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse
from urls.portal_websites import (
    ASPX_SEARCH_URLS,
)
import dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
import random
from curl_cffi.curl import CurlOpt
from itemloaders.processors import MapCompose, TakeFirst
import os


dotenv.load_dotenv()  # Add this line after imports


class AspxSpider(scrapy.Spider):
    name = "aspx_spider"
    allowed_domains = ["*"]
    start_urls = ["*"]
    
    settings = {
        # Rate limiting settings
        'DOWNLOAD_TIMEOUT': 300,  # 5 minutes
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429, 104, 403],
        'DOWNLOAD_DELAY': 15,
        'CONCURRENT_REQUESTS': 1,
        'REDIRECT_ENABLED': False,
        'COOKIES_ENABLED': True,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'HTTPCACHE_ENABLED': True,
        'HTTPCACHE_EXPIRATION_SECS': 86400,  # 24 hours
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
        },
        'RETRY_PRIORITY_ADJUST': -1,
        'COOKIES_DEBUG': True,
        'LOG_LEVEL': 'DEBUG',
        'CLOSESPIDER_TIMEOUT': 3600,  # 1 hour
        'CLOSESPIDER_ITEMCOUNT': 1000,
        'CLOSESPIDER_PAGECOUNT': 100,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Generate allowed_domains from START_URLS
        self.allowed_domains = list(
            {
                urlparse(url).netloc.split(":")[0]  # Remove port if present
                for url in ASPX_SEARCH_URLS
            }
        )
        self.failed_urls = set()

    def start_requests(self):
        for url in ASPX_SEARCH_URLS:
            if url not in self.failed_urls:
                yield scrapy.Request(
                    url=url, 
                    callback=self.search_form, 
                    meta={
                        "impersonate": "chrome120",
                        "dont_retry": False,
                        "handle_httpstatus_list": [403, 404, 500, 502, 503, 504],
                        "download_timeout": 300,
                        "verify": False,
                    },
                    errback=self.handle_error
                )

    def handle_error(self, failure):
        url = failure.request.url
        self.failed_urls.add(url)
        self.logger.error(f"Request failed for {url}: {failure.value}")

    def search_form(self, response):
        # self.logger.debug("""
        #     Impersonation Headers for Search Form:
        #     User-Agent: %s
        #     TLS Fingerprint: %s
        # """, 
        # response.request.headers.get('User-Agent'),
        # response.meta.get('impersonate'))
        viewstate = response.xpath('//input[@name="__VIEWSTATE"]/@value').get()
        if viewstate:
            pass
            self.logger.info(f"------the viewstate is {viewstate}-------")
        if not viewstate:
            self.logger.error(f"No viewstate found on page: {response.url}")
            return

        yield scrapy.FormRequest.from_response(
            response,
            formdata={
                "__VIEWSTATE": viewstate,
                'dateStart': '01/02/2025', 
                'dateEnd': '28/02/2025', 
                'cboSelectDateValue': 'DATE_DECISION',
                'csbtnSearch': 'Search',
                'rbGroup': 'rbRange'
            },
            callback=self.parse_results,
        )

    def parse_results(self, response):
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
                    "download_timeout": 300,
                    "max_retry_times": 3,
                    "retry_priority_adjust": -1,
                },
                cb_kwargs={"absolute_url": absolute_url},
                errback=self.handle_error
            )
        # Log basic response info
        self.logger.info(f"Status: {response.status}")
        self.logger.info(f"URL: {response.url}")

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