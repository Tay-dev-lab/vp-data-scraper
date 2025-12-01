import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse
from urls.portal_websites import (
    OCELLA_URLS,
)
import dotenv
from items.items import PlanningApplicationItem, clean_text
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose, TakeFirst

# dotenv.load_dotenv()  # Add this line after imports


class OcellaSpider(scrapy.Spider):
    name = "ocella_spider"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Generate allowed_domains from START_URLS
        self.allowed_domains = list(
            {
                urlparse(url).netloc.split(":")[0]  # Remove port if present
                for url in OCELLA_URLS
            }
        )

    def start_requests(self):
        for url in OCELLA_URLS:
            yield scrapy.Request(
                url=url, callback=self.search_form, meta={"impersonate": "chrome120"}
            )

    def search_form(self, response):
        yield scrapy.FormRequest(
            url=response.url.rsplit("/", 1)[0] + "/planningSearch",
            formdata={
                'reference': '',
                'location': '',
                'OcellaPlanningSearch.postcode': '',
                'area': '',
                'applicant': '',
                'agent': '',
                'receivedFrom': '',
                'receivedTo': '',
                'decidedFrom': '01-01-25',
                'decidedTo': '15-04-25',
                'action': 'Search'
            },
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-GB,en;q=0.5',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': response.url.rsplit("/", 2)[0],
                'Referer': response.url,
                'Connection': 'keep-alive'
            },
            callback=self.parse_results,
            dont_filter=True,
            errback=self.handle_error,
            meta={"impersonate": "chrome120"}
        )

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
        self.logger.error(f"Request URL: {failure.request.url}")
        self.logger.error(f"Request headers: {failure.request.headers}")
        self.logger.error(f"Request body: {failure.request.body}")

    def parse_results(self, response):
        links = response.xpath('//tr/td[1]/a[starts-with(@href, "planningDetails")]/@href').getall()
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
        loader.default_input_processor = MapCompose(clean_text)
        loader.default_output_processor = TakeFirst()

        # Application Details from table
        loader.add_value('application_url', absolute_url)
        loader.add_xpath('application_reference', '//tr[td/strong[contains(text(), "Reference")]]/td[2]/text()')
        loader.add_xpath('status', '//tr[td/strong[contains(text(), "Status")]]/td[2]/text()')
        loader.add_xpath('proposal', '//tr[td/strong[contains(text(), "Proposal")]]/td[2]/text()')
        loader.add_xpath('site_address', '//tr[td/strong[contains(text(), "Location")]]/td[2]/text()')
        loader.add_xpath('parish', '//tr[td/strong[contains(text(), "Parish")]]/td[2]/text()')
        loader.add_xpath('case_officer_name', '//tr[td/strong[contains(text(), "Case Officer")]]/td[2]/a/text()')
        loader.add_xpath('received_date', '//tr[td/strong[contains(text(), "Received")]]/td[2]/text()')
        loader.add_xpath('valid_from', '//tr[td/strong[contains(text(), "Validated")]]/td[2]/text()')
        loader.add_xpath('target_decision_date', '//tr[td/strong[contains(text(), "Decision By")]]/td[2]/text()')
        loader.add_xpath('decision_date', '//tr[td/strong[contains(text(), "Decided")]]/td[2]/text()')
        loader.add_xpath('applicant_name', '//tr[td/strong[contains(text(), "Applicant")]]/td[2]/text()')
        loader.add_xpath('agent_name', '//tr[td/strong[contains(text(), "Agent")]]/td[2]/text()')
        
        # Additional fields from table
        loader.add_xpath('application_type', '//tr[td/strong[contains(text(), "Application Type")]]/td[2]/text()')
        loader.add_xpath('development_type', '//tr[td/strong[contains(text(), "Development Type")]]/td[2]/text()')
        loader.add_xpath('ward', '//tr[td/strong[contains(text(), "Ward")]]/td[2]/text()')
        loader.add_xpath('location_coordinates', '//tr[td/strong[contains(text(), "Location Co-ordinates")]]/td[2]/text()')
        loader.add_xpath('appeal_submitted', '//tr[td/strong[contains(text(), "Appeal Submitted")]]/td[2]/text()')
        loader.add_xpath('appeal_decision', '//tr[td/strong[contains(text(), "Appeal Decision")]]/td[2]/text()')
        loader.add_xpath('division', '//tr[td/strong[contains(text(), "Division")]]/td[2]/text()')
        loader.add_xpath('existing_land_use', '//tr[td/strong[contains(text(), "Existing Land Use")]]/td[2]/text()')
        loader.add_xpath('proposed_land_use', '//tr[td/strong[contains(text(), "Proposed Land Use")]]/td[2]/text()')
        loader.add_xpath('agent_address', '//tr[td/strong[contains(text(), "Agent")]]/td[2]/text()')
        loader.add_xpath('applicant_address', '//tr[td/strong[contains(text(), "Applicant")]]/td[2]/text()')
        loader.add_xpath('committee_date', '//tr[td/strong[contains(text(), "Committee Date")]]/td[2]/text()')
        loader.add_xpath('conservation_area', '//tr[td/strong[contains(text(), "Conservation Area")]]/td[2]/text()')
        loader.add_xpath('determination_level', '//tr[td/strong[contains(text(), "Determination Level")]]/td[2]/text()')
        loader.add_xpath('environmental_assessment_required', '//tr[td/strong[contains(text(), "Environmental Assessment Required")]]/td[2]/text()')
        loader.add_xpath('expected_decision_level', '//tr[td/strong[contains(text(), "Expected Decision Level")]]/td[2]/text()')
        loader.add_xpath('expiry_date', '//tr[td/strong[contains(text(), "Expiry Date")]]/td[2]/text()')
        loader.add_xpath('extended_target_decision_date', '//tr[td/strong[contains(text(), "Extended Target Date")]]/td[2]/text()')
        loader.add_xpath('listed_building_grade', '//tr[td/strong[contains(text(), "Listed Building Grade")]]/td[2]/text()')
        loader.add_xpath('site_visit_date', '//tr[td/strong[contains(text(), "Site Visit Date")]]/td[2]/text()')
        loader.add_xpath('advert_expiry_date', '//tr[td/strong[contains(text(), "Advertisement Expiry Date")]]/td[2]/text()')

        # Extract consultation dates from Neighbours row
        neighbours_text = response.xpath('//tr[td/strong[contains(text(), "Neighbours")]]/td[2]/text()').get()
        if neighbours_text:
            loader.add_value('consultation_start_date', neighbours_text.split(':')[1].split(',')[0].strip())
            loader.add_value('consultation_expiry_date', neighbours_text.split(':')[2].strip())
        
        # Add URL
        

        yield loader.load_item()
