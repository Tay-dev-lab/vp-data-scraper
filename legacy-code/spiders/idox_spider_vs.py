import scrapy
from urllib.parse import urlparse
from urls.portal_websites import (
    IDOX_1,
)
import dotenv
from dotenv import load_dotenv
from items.items import PlanningApplicationItem
from scrapy.loader import ItemLoader
import logging
from rich.logging import RichHandler
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
import os
from datetime import datetime


dotenv.load_dotenv(override=True)

# Configure rich logging with console output only
console = Console()

# Set up rich handler for console
rich_handler = RichHandler(rich_tracebacks=True, markup=True)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[rich_handler]  # Only use rich handler
)

# Get logger for this module
logger = logging.getLogger('idox_spider')

class IdoxSpider(scrapy.Spider):
    name = "idox_spider"
    
    # Optimized custom settings for better performance
    custom_settings = {
        'CONCURRENT_REQUESTS': 16,  # Increase concurrent requests
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,  # Limit per domain to avoid overloading
        'DOWNLOAD_DELAY': 0.5,  # Moderate delay between requests
        'COOKIES_ENABLED': True,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'AUTOTHROTTLE_ENABLED': True,  # Enable autothrottle
        'AUTOTHROTTLE_START_DELAY': 1.0,  # Starting delay
        'AUTOTHROTTLE_MAX_DELAY': 3.0,  # Maximum delay
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 4.0,  # Target concurrency
        'DOWNLOAD_TIMEOUT': 30,  # Timeout for requests
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
        # Enable the CustomProxyMiddleware
        'DOWNLOADER_MIDDLEWARES': {
            'middlewares.CustomProxyMiddleware': 50,
            'middlewares.Handle202Middleware': 351,
        },
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define default headers for requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-GB,en;q=0.5',
            # 'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': '{domain}',
            'Connection': 'keep-alive',
            'Referer': '{domain}/online-applications/search.do?action=advanced',
            # 'Cookie': 'JSESSIONID=sRBjeVSCwXcsHEyFKmNaRP0vjBl-1spbhcc4t2Cg.kc-pawlive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Priority': 'u=0, i',
        }

        self.allowed_domains = list(
            {
                urlparse(url).netloc.split(":")[0]  # Remove port if present
                for url in IDOX_1
            }
        )
        
        # Log the proxy value from environment variable with Rich
        proxy_value = dotenv.get_key(dotenv.find_dotenv(), "sticky")
        logger.info(f"Initialized spider with proxy from env: {proxy_value}")
        console.log(f"[bold green]Initialized spider with proxy from env:[/bold green] [yellow]{proxy_value}[/yellow]")
        
        # Log to console
        logger.info(f"Spider {self.name} initialized with {len(IDOX_1)} URLs")
        
        rprint(Panel.fit(
            f"[bold]IDOX Spider Initialized[/bold]\nProxy: {proxy_value}\nTargeting {len(IDOX_1)} URLs",
            title="Spider Configuration",
            border_style="blue"
        ))
    
    def start_requests(self):
        """Generate initial requests for each council"""
        for url in IDOX_1:
            council_name = self.extract_council_name(url)
            console.log(f"[bold blue]Starting scrape for council:[/bold blue] [cyan]{council_name}[/cyan]")
            
            request = scrapy.Request(
                url=url,
                callback=self.parse_search_form,
                cb_kwargs={'council_name': council_name},
                dont_filter=True,
            )
            
            # Log that we're sending a request with proxy
            console.log(f"[dim]Sending request to[/dim] [link={url}]{url}[/link] [dim](proxy will be added by middleware)[/dim]")
            
            yield request

    # Add a new method to log proxy information for each request
    def _log_request_proxy(self, request, spider):
        """Log proxy information for debugging"""
        proxy = request.meta.get('proxy', 'No proxy set')
        self.logger.debug(f"Request to {request.url} using proxy: {proxy}")
        return request

    def extract_council_name(self, url):
        """Extract council name from URL"""
        # Remove http(s):// and .gov.uk
        domain = url.split('://')[1].split('.gov.uk')[0]
        # Remove common prefixes
        for prefix in ['pa.', 'publicaccess.', 'planning.', 'planningonline.']:
            if domain.startswith(prefix):
                domain = domain[len(prefix):]
        return domain

    def parse_search_form(self, response, council_name):
        """Parse the search form and submit search"""
        # Log if proxy was used for this response
        proxy_used = response.meta.get('proxy', 'No proxy in response meta')
        console.log(f"[bold green]Response received[/bold green] from [link={response.url}]{response.url}[/link]")
        console.log(f"[bold magenta]Proxy used:[/bold magenta] [yellow]{proxy_used}[/yellow]")
        
        csrf_token = response.css('input[name="_csrf"]::attr(value)').get()
        
        # Fix form data structure
        formdata = {
            '_csrf': csrf_token,
            'searchType': 'Application',
            'action': 'search',  # Uncomment this
            'caseAddressType': "Application",
            'searchCriteria.decision': 'Decision',
            'date(applicationDecisionStart)': '01/01/2025',  # Fix syntax
            'date(applicationDecisionEnd)': '15/04/2025'
            # Remove redundant 'decision' field
        }
        
        # Ensure no None values
        formdata = {k: str(v) if v is not None else '' for k, v in formdata.items()}
        
        # Update headers with proper domain formatting
        domain = urlparse(response.url).netloc
        headers = self.headers.copy()
        headers['Origin'] = f'https://{domain}'
        headers['Referer'] = response.url
        
        search_url = response.urljoin('advancedSearchResults.do?action=firstPage')
        yield scrapy.FormRequest(
            url=search_url,
            formdata=formdata,
            headers=headers,
            callback=self.parse_search_results,
            cb_kwargs={'council_name': council_name},
            dont_filter=True
        )

    def parse_search_results(self, response, council_name):
        """Parse search results page"""
        results = response.css('li.searchresult')
        
        # Use Rich to log results with color
        if results:
            console.log(f"[bold green]Found {len(results)} results[/bold green] on current page for [cyan]{council_name}[/cyan]")
        else:
            console.log(f"[bold red]No results found[/bold red] on current page for [cyan]{council_name}[/cyan]")
        
        # Log proxy information for this response
        proxy_used = response.meta.get('proxy', 'No proxy in response meta')
        console.log(f"[dim]Results page using proxy:[/dim] [yellow]{proxy_used}[/yellow]")
        
        for result in results:
            app_url = result.css('a::attr(href)').get()
            if app_url:
                loader = ItemLoader(item=PlanningApplicationItem())
                
                # Use correct field names from PlanningApplicationItem
                loader.add_value('council_name', council_name)
                loader.add_value('application_reference', result.css('p.metaInfo::text').re_first(r'Ref\. No:\s*([^\n]*)'))
                loader.add_value('proposal', result.css('p.description::text').get('').strip())
                loader.add_value('status', result.css('p.metaInfo::text').re_first(r'Status:\s*([^\n]*)'))
                loader.add_value('valid_from', result.css('p.metaInfo::text').re_first(r'Validated:\s*([^\n]*)'))
                loader.add_value('decision_date', result.css('p.metaInfo::text').re_first(r'Decision:\s*([^\n]*)'))
                loader.add_value('decision', result.css('p.metaInfo::text').re_first(r'Decision:\s*([^\n]*)'))
                loader.add_value('application_url', response.urljoin(app_url))  # Changed from 'url' to 'application_url'
                
                yield scrapy.Request(
                    url=response.urljoin(app_url),
                    callback=self.parse_application_details,
                    cb_kwargs={'loader': loader}
                )

        # Follow next page if it exists
        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            console.log(f"[bold blue]Following next page[/bold blue] for [cyan]{council_name}[/cyan]")
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_search_results,
                cb_kwargs={'council_name': council_name}
            )

    def parse_application_details(self, response, loader):
        """Parse the application details pages"""
        # Update the loader with the response selector
        loader.selector = response.selector
        
        # Log that we're processing the Application Details page
        console.log(f"[bold blue]Processing Application Details page[/bold blue]")
        
        # First try to extract proposal and address from the addressCrumb div
        proposal = response.css('div.addressCrumb span.description::text').get()
        if proposal:
            proposal = proposal.strip()
            loader.add_value('proposal', proposal)
            console.log(f"[dim]Added proposal from addressCrumb:[/dim] [yellow]{proposal}[/yellow]")
        
        address = response.css('div.addressCrumb span.address::text').get()
        if address:
            address = address.strip()
            loader.add_value('site_address', address)
            console.log(f"[dim]Added site_address from addressCrumb:[/dim] [yellow]{address}[/yellow]")
        
        # Create a mapping of field names to item field names for the main details
        main_field_mapping = {
            'Reference': 'application_reference',
            'Application Received': 'registration_date',
            'Application Validated': 'valid_from',
            'Address': 'site_address',
            'Proposal': 'proposal',
            'Status': 'status',
            'Decision': 'decision',
            'Decision Issued Date': 'decision_date',
            'Appeal Status': 'appeal_submitted',
            'Appeal Decision': 'appeal_decision'
        }
        
        # Extract status from the status span if it exists
        status = response.xpath("//span[@class='caseDetailsStatus']/text()").get()
        if status:
            loader.add_value('status', status)
            console.log(f"[dim]Added status from span:[/dim] [yellow]{status}[/yellow]")
        
        # Target the simpleDetailsTable specifically for summary information
        summary_table = response.xpath("//table[@id='simpleDetailsTable']//tr")
        console.log(f"[bold blue]Found {len(summary_table)} rows[/bold blue] in the summary details table")
        
        # Process each row in the summary table
        for row in summary_table:
            # Extract the field name and value with better handling of whitespace
            field_name = row.xpath("normalize-space(.//th/text())").get('')
            
            # Handle the special case for Status which might contain a span
            if field_name == 'Status':
                field_value = row.xpath("normalize-space(.//td//span/text())").get('')
                if not field_value:
                    field_value = row.xpath("normalize-space(.//td/text())").get('')
            else:
                field_value = row.xpath("normalize-space(.//td/text())").get('')
            
            # Skip "Not Available" and "Unknown" values
            if field_name and field_value and field_value not in ["Not Available", "Unknown"]:
                # Check if we have a mapping for this field
                if field_name in main_field_mapping:
                    item_field = main_field_mapping[field_name]
                    # Skip proposal and site_address fields since we already extracted them directly
                    if item_field not in ['proposal', 'site_address'] or (item_field == 'proposal' and not proposal) or (item_field == 'site_address' and not address):
                        loader.add_value(item_field, field_value)
                        console.log(f"[dim]Added summary field:[/dim] [cyan]{field_name}[/cyan] → [green]{item_field}[/green]: [yellow]{field_value}[/yellow]")
                else:
                    # Log unknown fields for future reference
                    self.logger.debug(f"Unknown summary field: {field_name} with value: {field_value}")
                    console.log(f"[bold red]Unknown summary field:[/bold red] [cyan]{field_name}[/cyan] with value: [yellow]{field_value}[/yellow]")
        
        # Follow Further Information tab
        further_info_url = response.xpath("//a[@id='subtab_details']/@href").get()
        if further_info_url:
            yield scrapy.Request(
                url=response.urljoin(further_info_url),
                callback=self.parse_further_info,
                cb_kwargs={'loader': loader}
            )
        else:
            yield loader.load_item()

    def parse_further_info(self, response, loader):
        """Parse the Further Information tab"""
        # Update the loader with the response selector
        loader.selector = response.selector
        
        # Log that we're processing the Further Information tab
        console.log(f"[bold blue]Processing Further Information tab[/bold blue]")
        
        # Create a mapping of field names to item field names
        field_mapping = {
            'Application Type': 'application_type',
            'Decision': 'decision',
            'Actual Decision Level': 'determination_level',
            'Expected Decision Level': 'expected_decision_level',
            'Case Officer': 'case_officer_name',
            'Parish': 'parish',
            'Community': 'parish',
            'Ward': 'ward',

            'Applicant Name': 'applicant_name',
            'Applicant Address': 'applicant_address',
            'Agent Name': 'agent_name',
            'Agent Company Name': 'agent_company_name',
            'Agent Address': 'agent_address',
            'Environmental Assessment Requested': 'environmental_assessment_required'
        }
        
        # Target the applicationDetails table specifically
        details_table = response.xpath("//table[@id='applicationDetails']//tr")
        console.log(f"[bold blue]Found {len(details_table)} rows[/bold blue] in the application details table")
        
        # Process each row in the details table
        for row in details_table:
            # Extract the field name and value with better handling of whitespace
            field_name = row.xpath("normalize-space(.//th/text())").get('')
            field_value = row.xpath("normalize-space(.//td/text())").get('')
            
            # Skip "Not Available" values
            if field_name and field_value and field_value != "Not Available":
                # Check if we have a mapping for this field
                if field_name in field_mapping:
                    item_field = field_mapping[field_name]
                    loader.add_value(item_field, field_value)
                    console.log(f"[dim]Added field:[/dim] [cyan]{field_name}[/cyan] → [green]{item_field}[/green]: [yellow]{field_value}[/yellow]")
                else:
                    # Log unknown fields for future reference
                    self.logger.debug(f"Unknown field: {field_name} with value: {field_value}")
                    console.log(f"[bold red]Unknown field:[/bold red] [cyan]{field_name}[/cyan] with value: [yellow]{field_value}[/yellow]")
        
        # Follow Contacts tab
        contacts_url = response.xpath("//a[@id='subtab_contacts']/@href").get()
        if contacts_url:
            yield scrapy.Request(
                url=response.urljoin(contacts_url),
                callback=self.parse_contacts,
                cb_kwargs={'loader': loader}
            )
        else:
            yield loader.load_item()

    def parse_contacts(self, response, loader):
        """Parse the Contacts tab"""
        # Update the main loader with response selector
        loader.selector = response.selector
        
        # Extract agent details
        agent_section = response.xpath("//div[@class='agents']")
        if agent_section:
            loader.add_xpath('agent_name', "//div[@class='agents']//p/text()")
            
            # Only extract agent_address if there's an exact match for the Address field
            address_exists = response.xpath("//div[@class='agents']//th[text()='Address']").get()
            if address_exists:
                loader.add_xpath('agent_address', "//div[@class='agents']//th[text()='Address']/following-sibling::td/text()")
            
            # Use case-insensitive match for Email
            loader.add_xpath('agent_email', "//div[@class='agents']//th[contains(translate(text(), 'EMAIL', 'email'), 'email')]/following-sibling::td/text()")
            
            # Be more specific for phone/mobile
            loader.add_xpath('agent_phone', "//div[@class='agents']//th[contains(text(), 'Phone') or contains(text(), 'Mobile Number')]/following-sibling::td/text()")
        
        # Follow Dates tab
        dates_url = response.xpath("//a[@id='subtab_dates']/@href").get()
        if dates_url:
            yield scrapy.Request(
                url=response.urljoin(dates_url),
                callback=self.parse_dates,
                cb_kwargs={'loader': loader}
            )
        else:
            yield loader.load_item()

    def parse_dates(self, response, loader):
        """Parse the Important Dates tab"""
        # Update the loader with the response selector
        loader.selector = response.selector
        
        # Create a mapping of date field names to item field names
        date_field_mapping = {
            'Application Received Date': 'registration_date',
            'Application Validated Date': 'valid_from',
            'Expiry Date': 'expiry_date',
            'Actual Committee Date': 'committee_date',
            'Latest Neighbour Consultation Date': 'consultation_start_date',
            'Neighbour Consultation Expiry Date': 'consultation_expiry_date',
            'Standard Consultation Date': 'consultation_start_date',
            'Standard Consultation Expiry Date': 'consultation_expiry_date',
            'Last Advertised In Press Date': 'press_notice_start_date',
            'Latest Advertisement Expiry Date': 'advert_expiry_date',
            'Last Site Notice Posted Date': 'site_notice_date',
            'Latest Site Notice Expiry Date': 'publicity_end_date',
            'Internal Target Date': 'target_decision_date',
            'Agreed Expiry Date': 'statutory_expiry_date',
            'Decision Made Date': 'decision_date',
            'Decision Issued Date': 'decision_date',
            'Permission Expiry Date': 'decision_expiry_date',
            'Decision Printed Date': 'dispatch_date',
            'Environmental Impact Assessment Received': 'environmental_assessment_required',
            'Determination Deadline': 'decision_due_date',
            'Temporary Permission Expiry Date': 'extension_date'
        }
        
        # Log the number of date fields found
        dates_table = response.xpath("//table[@id='simpleDetailsTable']//tr")
        console.log(f"[bold blue]Found {len(dates_table)} date fields[/bold blue] in the Dates tab")
        
        # Process each row in the dates table
        for row in dates_table:
            # Extract the date type and value with better handling of whitespace
            date_type = row.xpath("normalize-space(.//th/text())").get('')
            date_value = row.xpath("normalize-space(.//td/text())").get('')
            
            # Skip "Not Available" values
            if date_type and date_value and date_value != "Not Available":
                # Check if we have a mapping for this date field
                if date_type in date_field_mapping:
                    field_name = date_field_mapping[date_type]
                    loader.add_value(field_name, date_value)
                    console.log(f"[dim]Added date field:[/dim] [cyan]{date_type}[/cyan] → [green]{field_name}[/green]: [yellow]{date_value}[/yellow]")
                else:
                    # Log unknown date fields for future reference
                    self.logger.debug(f"Unknown date field: {date_type} with value: {date_value}")
                    console.log(f"[bold red]Unknown date field:[/bold red] [cyan]{date_type}[/cyan] with value: [yellow]{date_value}[/yellow]")
        
        yield loader.load_item()