import scrapy
from scrapy.http import Response
from scrapy.spiders import CrawlSpider
from urllib.parse import urlparse
from urls.portal_websites import (
    PLANNING_SEARCH_URLS,
)
import dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader

dotenv.load_dotenv()  # Add this line after imports


class SearchSpider(scrapy.Spider):
    name = "search_spider"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize with domains from initial URLs
        self.allowed_domains = list(
            {urlparse(url).hostname for url in PLANNING_SEARCH_URLS}
        )
        self.logger.debug(f"Initial allowed domains: {self.allowed_domains}")
        # Track processed domains
        self.seen_domains = set(self.allowed_domains)

    def process_redirect(self, response):
        # Extract domain from current response
        current_domain = urlparse(response.url).hostname

        # Add new domain to allowed domains if not already present
        if current_domain and current_domain not in self.seen_domains:
            self.allowed_domains.append(current_domain)
            self.seen_domains.add(current_domain)
            self.logger.debug(f"Added new allowed domain: {current_domain}")

    def start_requests(self):
        for url in PLANNING_SEARCH_URLS:
            yield scrapy.Request(
                url=url, callback=self.get_token, meta={"impersonate": "chrome120"}
            )

    def get_token(self, response):
        token = response.css(
            'input[name="__RequestVerificationToken"]::attr(value)'
        ).get()
        if token:
            self.logger.info(f"------the response url is {response.url}-------")
        if not token:
            self.logger.error(f"No token found on page: {response.url}")
            return

        yield scrapy.FormRequest(
            url=response.url.rsplit("/", 1)[0] + "/Results",
            formdata={
                "DateDeterminedFrom": "17/02/2025",
                "DateDeterminedTo": "19/02/2025",
                "__RequestVerificationToken": token,
                "AdvancedSearch": "True",
                "SearchPlanning": "true",
                "SearchBuildingControl": "false",
                "SearchAppeals": "false",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": response.url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.5",
                "Origin": f"https://{self.allowed_domains[0]}",
            },
            callback=self.parse_results,
            dont_filter=True,
            meta={
                "dont_redirect": False,
                "handle_httpstatus_list": [302, 200],
                "impersonate": "chrome120",
            },
            errback=self.handle_error,
        )

    def parse_results(self, response):
        self.logger.info(f"Processing results from URL: {response.url}")
        self.logger.info(f"Response status: {response.status}")

        # Check if we've been redirected to main site search
        if "/site-search" in response.url:
            self.logger.warning(
                "Redirected to main site search - form submission failed"
            )
            return

        # Get all planning application links on current page using multiple XPath expressions
        links = response.xpath(
            # Original XPath
            "//a[contains(@aria-label, 'View planning')]/@href | "
            # Additional XPath for absolute path
            #"/html/body/div[5]/div/div[4]/div[1]/div/div/div/div/div/div[1]/a/@href"
            # Additional XPath for alternative aria-label
            "//a[contains(@aria-label, 'Planning application')]/@href"
        ).getall()

        if not links:
            self.logger.warning(f"No links found on page: {response.url}")
            with open("debug_response.html", "wb") as f:
                f.write(response.body)
        else:
            self.logger.info(f"Found {len(links)} planning application links")

            # Process current page links
            for link in links:
                absolute_url = response.urljoin(link)
                self.logger.debug(f"Following link: {absolute_url}")
                yield scrapy.Request(
                    url=absolute_url,
                    callback=self.parse_plan_apps,
                    meta={"impersonate": "chrome120"},
                    dont_filter=True,
                )

        # Handle pagination using data-ajax-target
        next_page = response.xpath(
            '//div[contains(@class, "pagination")]//a[@aria-label="Next Page."]/@data-ajax-target | '
            '//a[@aria-label="Next page."]/@href'
        ).get()

        if next_page:
            next_url = response.urljoin(next_page)
            self.logger.info(f"Following next page: {next_url}")

            # Add params to URL if they're not already there
            if "module=PLA" not in next_url:
                next_url = f"{next_url}{'&' if '?' in next_url else '?'}module=PLA"

            yield scrapy.Request(
                url=next_url,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": response.url,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-GB,en;q=0.5",
                    "Origin": f"https://{self.allowed_domains[0]}",
                    "X-Requested-With": "XMLHttpRequest",  # Add this for AJAX requests
                },
                callback=self.parse_results,
                dont_filter=True,
                meta={
                    "dont_redirect": False,
                    "handle_httpstatus_list": [302, 200],
                    "impersonate": "chrome120",
                },
                errback=self.handle_error,
            )
        else:
            self.logger.info("No next page found - reached end of pagination")

    def handle_error(self, failure):
        self.logger.error(f"Request failed: {failure.value}")
        self.logger.error(f"Request URL: {failure.request.url}")
        self.logger.error(f"Request headers: {failure.request.headers}")
        self.logger.error(f"Request body: {failure.request.body}")

    def parse_plan_apps(self, response):
        loader = ItemLoader(item=PlanningApplicationItem(), response=response)
        
        # Add the application URL
        loader.add_value('application_url', response.url)
        
        # Basic Details - Adding fallback selectors based on the provided HTML structure
        loader.add_xpath(
            "application_reference",
            """//td[contains(text(), 'Application Number')]//following-sibling::td/text() |
               //td[contains(text(), 'Application Number')]//div[@class='twinrowsize']/span/text() |
               //h1[contains(@class, 'pageTitle')]/text()"""
        )

        loader.add_xpath(
            "application_type",
            """//td[contains(text(), 'Application Type')]//following-sibling::td/text() |
               //td[contains(text(), 'Application Type')]//div[@class='twinrowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Application Type']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "status",
            """//td[contains(text(), 'Status')]//following-sibling::td/text() |
               //td[contains(text(), 'Status')]//div[@class='twinrowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Status']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "determination_level",
            """//td[contains(text(), 'Decision Level')]//following-sibling::td/text() |
               //td[contains(text(), 'Decision Level')]//div[@class='twinrowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Decision Level']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "site_address",
            """//td[contains(text(), 'Location')]//following-sibling::td/text() |
               //td[contains(text(), 'Location Address')]//following-sibling::td/text() |
               //td[contains(text(), 'Location')]//div[@class='singlerowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Location']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "proposal",
            """//td[contains(text(), 'Proposal')]//following-sibling::td/text() |
               //td[contains(text(), 'Proposal')]//div[@class='singlerowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Proposal']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "parish",
            """//td[contains(text(), 'Parish')]//following-sibling::td/text() |
               //td[contains(text(), 'Parish')]//div[@class='twinrowsize']/span/text() |
               //td[contains(text(), 'Parish')]//following-sibling::td//a/text() |
               //td[@class='halfWidth']/label[text()='Parish']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "ward",
            """//td[contains(text(), 'Ward')]//following-sibling::td/text() |
               //td[contains(text(), 'Ward')]//div[@class='twinrowsize']/span/text() |
               //td[contains(text(), 'Ward')]//following-sibling::td//a/text() |
               //td[@class='halfWidth']/label[text()='Ward']/following-sibling::div[@class='icmltext displayText displayTextArea wrappedText']/ul/li/text()"""
        )

        loader.add_xpath(
            "received_date",
            """//td[contains(text(), 'Received Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Received Date')]//div[@class='twinrowsize']/span/text() |
               //td[@class='45Width']/label[text()='Date Received']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        loader.add_xpath(
            "valid_from",
            """//td[contains(text(), 'Valid Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Application Valid')]//following-sibling::td/text() |
               //td[contains(text(), 'Valid Date')]//div[@class='twinrowsize']/span/text() |
               //td[@class='45Width']/label[text()='Date Valid']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        loader.add_xpath(
            "target_decision_date",
            """//td[contains(text(), 'Target Decision Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Target Decision Date')]//div[@class='twinrowsize']/span/text()"""
        )

        loader.add_xpath(
            "decision",
            """//td[contains(text(), 'Decision')]//following-sibling::td/text() |
               //td[contains(text(), 'Decision')]//div[@class='twinrowsize']/span/text() |
               //table[contains(@class, 'progressBarTbl')]//tr/td[text()!='N/A'][normalize-space()] |
               //td[@class='halfWidth']/label[text()='Decision']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "decision_date",
            """//td[contains(text(), 'Decision Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Decision Issued Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Decision Date')]//div[@class='twinrowsize']/span/text() |
               //td[contains(text(), 'Decision Issued Date')]//div[@class='twinrowsize']/span/text() |
               //td[@class='45Width']/label[text()='Decision Date']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        # Applicant Details
        loader.add_xpath(
            "applicant_name",
            """//td[contains(text(), 'Applicant')]//following-sibling::td/text() |
               //td[contains(text(), 'Applicant')]//div[@class='singlerowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Applicant']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "applicant_address",
            """//td[contains(text(), "Applicant's Address")]//following-sibling::td/text() |
               //td[contains(text(), "Applicant's Address")]//div[@class='singlerowsize']/span/text() |
               //td[@class='halfWidth']/label[text()="Applicant's Address"]/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        loader.add_xpath(
            "agent_name",
            """//td[contains(text(), 'Agent')]//following-sibling::td/text() |
               //td[contains(text(), 'Agent')]//div[@class='singlerowsize']/span/text() |
               //td[@class='halfWidth']/label[text()='Agent']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )

        # Additional date fields
        loader.add_xpath(
            "consultation_start_date",
            """//td[contains(text(), 'Consultation Start Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Consultation Start')]//div[@class='twinrowsize']/span/text()"""
        )

        loader.add_xpath(
            "site_visit_date",
            """//td[contains(text(), 'Site Visited')]//following-sibling::td/text() |
               //td[contains(text(), 'Site Notice Date')]//following-sibling::td/text() |
               //td[@class='45Width']/label[text()='Site Notice Expiry Date']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        loader.add_xpath(
            "consultation_expiry_date",
            """//td[contains(text(), 'Consultation End')]//following-sibling::td/text() |
               //td[contains(text(), 'Consultation Expiry')]//following-sibling::td/text() |
               //td[@class='45Width']/label[text()='Consultation Expiry Date']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        loader.add_xpath(
            "advert_expiry_date",
            """//td[contains(text(), 'Advert Expiry')]//following-sibling::td/text() |
               //td[contains(text(), 'Advertisement Expiry')]//following-sibling::td/text() |
               //td[@class='45Width']/label[text()='Advert Expiry Date']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        loader.add_xpath(
            "committee_date",
            """//td[contains(text(), 'Committee Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Committee Meeting')]//following-sibling::td/text() |
               //td[@class='45Width']/label[text()='Committee Date']/following-sibling::div[@class='icmltext displayText']/span/text()"""
        )

        loader.add_xpath(
            "expiry_date",
            """//td[contains(text(), 'Expiry Date')]//following-sibling::td/text() |
               //td[contains(text(), 'Application Expiry')]//following-sibling::td/text()"""
        )

        # Additional details
        loader.add_xpath(
            "expected_decision_level",
            """//td[contains(text(), 'Expected Decision Level')]//following-sibling::td/text() |
               //td[contains(text(), 'Decision Level')]//following-sibling::td/text()"""
        )

        loader.add_xpath(
            "case_officer_name",
            """//td[contains(text(), 'Case Officer')]//following-sibling::td/text() |
               //td[contains(text(), 'Officer')]//following-sibling::td/text() |
               //td[@class='halfWidth']/label[text()='Case Officer']/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )
        

        loader.add_xpath(
            "conservation_area",
            """//td[contains(text(), 'Conservation Area')]//following-sibling::td/text() |
               //td[contains(text(), 'Conservation')]//following-sibling::td/text()"""
        )

        loader.add_xpath(
            "listed_building_grade",
            """//td[contains(text(), 'Listed Building Grade')]//following-sibling::td/text() |
               //td[contains(text(), 'Listed Building')]//following-sibling::td/text()"""
        )

        loader.add_xpath(
            "agent_address",
            """//td[contains(text(), 'Agent Address')]//following-sibling::td/text() |
               //td[contains(text(), "Agent's Address")]//following-sibling::td/text() |
               //td[@class='halfWidth']/label[text()="Agent's Address"]/following-sibling::div[@class='icmltext displayText wrappedText']/span/text()"""
        )
        

    
        # Add debug logging
        self.logger.debug(f"Extracted data from URL: {response.url}")
        return loader.load_item()
