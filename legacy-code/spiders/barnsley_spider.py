import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse
from urls.portal_websites import (
    BARSNLEY_URLS,
)
import dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader

dotenv.load_dotenv()  # Add this line after imports


class BarnsleySpider(scrapy.Spider):
    name = "barnsley_spider"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Generate allowed_domains from START_URLS
        self.allowed_domains = list(
            {
                urlparse(url).netloc.split(":")[0]  # Remove port if present
                for url in BARSNLEY_URLS
            }
        )

    def start_requests(self):
        for url in BARSNLEY_URLS:
            yield scrapy.Request(
                url=url, callback=self.search_form, meta={"impersonate": "chrome120"}
            )

    def search_form(self, response):
        yield scrapy.FormRequest.from_response(
            response,
            formdata={
                "dateDecisionTo": "12/02/2025",
                "dateDecisionFrom": "10/02/2025",
                "submit": "Search",
            },
            callback=self.parse_results,
        )

    def parse_results(self, response):
        links = response.css(
            "#table1 tbody:nth-child(2) tr.trow--planning td:nth-child(1) a::attr(href)"
        ).getall()
        for link in links:
            # Convert relative URLs to absolute URLs
            absolute_url = response.urljoin(link)
            yield scrapy.Request(
                url=absolute_url,
                callback=self.parse_plan_apps,
                meta={"impersonate": "chrome120"},
                cb_kwargs={"absolute_url": absolute_url}
            )
        # Log basic response info
        self.logger.info(f"Status: {response.status}")
        self.logger.info(f"URL: {response.url}")

    def parse_plan_apps(self, response, absolute_url):
        loader = ItemLoader(item=PlanningApplicationItem(), response=response)
        
        # Add the application URL
        loader.add_value('application_url', absolute_url)
        
        # Add all fields using exact XPath text matching with [1] to get only first occurrence
        loader.add_xpath(
            "application_reference",
            '//td[@class="col-xs-3"][text()="Application Reference Number"]/following-sibling::td[@class="col-xs-9"]/text()[1]',
        )
        loader.add_xpath(
            "proposal",
            '//td[@class="col-xs-3"][text()="Description"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "site_address",
            '//td[@class="col-xs-3"][text()="Site Address"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "received_date",
            '//td[@class="col-xs-3"][text()="Received Date"]/following-sibling::td[@class="col-xs-9"]/text()[1]',
        )
        loader.add_xpath(
            "valid_from",
            '//td[@class="col-xs-3"][text()="Valid From"]/following-sibling::td[@class="col-xs-9"]/text()[1]',
        )
        loader.add_xpath(
            "decision",
            '//td[@class="col-xs-3"][text()="Decision"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "status",
            '//td[@class="col-xs-3"][text()="Status"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "applicant_name",
            '//td[@class="col-xs-3"][text()="Applicant Name"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "applicant_address",
            '//td[@class="col-xs-3"][text()="Applicant Address"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "parish",
            '//td[@class="col-xs-3"][text()="Parish"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "ward",
            '//td[@class="col-xs-3"][text()="Ward"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "application_type",
            '//td[@class="col-xs-3"][text()="Application Type"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "determination_level",
            '//td[@class="col-xs-3"][text()="Determination Level"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "agent_name",
            '//td[@class="col-xs-3"][text()="Agent Name"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
 
        loader.add_xpath(
            "environmental_assessment_required",
            '//td[@class="col-xs-3"][text()="Environmental Assessment Required"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "consultation_expiry_date",
            '//td[@class="col-xs-3"][text()="Consultation Expiry Date"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "target_decision_date",
            '//td[@class="col-xs-3"][text()="Target Decision Date"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "extended_target_decision_date",
            '//td[@class="col-xs-3"][text()="Extended Target Decision Date"]/following-sibling::td[@class="col-xs-9"]/text()',
        )
        loader.add_xpath(
            "decision_date",
            '//td[@class="col-xs-3"][text()="Decision Date"]/following-sibling::td[@class="col-xs-9"]/text()',
        )

        return loader.load_item()
