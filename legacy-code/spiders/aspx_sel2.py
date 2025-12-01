import asyncio
import logging
import nest_asyncio
from datetime import datetime
from selenium_driverless import webdriver
import sys
import os
from bs4 import BeautifulSoup
import scrapy
from scrapy import Request, FormRequest
from twisted.internet import threads
from urllib.parse import urlparse
from scrapy.loader import ItemLoader
from itemloaders.processors import MapCompose, TakeFirst
import traceback

# Apply nest_asyncio to allow nested event loops
nest_asyncio.apply()

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from items.items import PlanningApplicationItem
from urls.portal_websites import ASPX_SEARCH_URLS

# Setup logging
logging.basicConfig(level="INFO", format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger(__name__)

def get_domain(url):
    """Extract domain from URL using urllib.parse"""
    parsed = urlparse(url)
    domain = parsed.netloc
    # Remove port number if present
    if ':' in domain:
        domain = domain.split(':')[0]
    return domain

class ViewstateManager:
    def __init__(self):
        self.tokens = {}
        self.cookies = {}
        self.special_urls = {}
        self.form_data = {}

    async def get_token_for_url(self, url):
        """Get tokens and cookies for the given URL"""
        domain = get_domain(url)
        log.info(f"Getting token for {url} (domain: {domain})")
        
        # Return cached tokens if available
        if domain in self.tokens and domain in self.cookies:
            log.info(f"Using cached token for {domain}")
            return self.tokens[domain], self.cookies[domain]
        
        # Determine if this is a Cloudflare site
        is_cloudflare = any(cf_domain in domain for cf_domain in ['camden.gov.uk', 'planningexplorer.barnet.gov.uk'])
        wait_time = 15 if is_cloudflare else 5
        
        try:
            # Setup Chrome options
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--start-maximized")
            
            # Add anti-detection measures for all sites (won't hurt normal sites)
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Create debug file
            with open(f'browser_debug_{domain}.txt', 'w') as f:
                f.write(f"Attempting to open browser for {url} at {datetime.now().isoformat()}\n")
                f.write(f"Chrome options: {options.arguments}\n")
            
            log.info(f"BROWSER: Launching Chrome for {domain} at {datetime.now().isoformat()}")
            
            # Launch Chrome
            driver = await webdriver.Chrome(options=options)
            
            with open(f'browser_debug_{domain}.txt', 'a') as f:
                f.write(f"Browser launched at {datetime.now().isoformat()}\n")
            
            log.info(f"BROWSER: Chrome launched successfully for {domain}")
            log.info(f"BROWSER: Navigating to {url}")
            
            # Navigate to URL
            await driver.get(url)
            log.info(f"BROWSER: URL loaded for {domain}")
            
            # Take screenshot
            try:
                screenshot_path = f'screenshot_{domain}.png'
                await driver.save_screenshot(screenshot_path)
                log.info(f"BROWSER: Screenshot saved to {screenshot_path}")
            except Exception as e:
                log.error(f"BROWSER: Failed to save screenshot: {e}")
            
            # Wait for page to load
            log.info(f"BROWSER: Waiting {wait_time} seconds for page to load completely for {domain}")
            await asyncio.sleep(wait_time)
            
            # Check for Cloudflare challenge page
            page_source = await driver.page_source
            if "Checking your browser" in page_source or "Just a moment" in page_source:
                log.warning(f"BROWSER: Detected Cloudflare challenge, waiting 10 more seconds")
                await asyncio.sleep(10)
                page_source = await driver.page_source
            
            # Get cookies
            cookies = await driver.get_cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            self.cookies[domain] = cookie_dict
            log.info(f"BROWSER: Retrieved {len(cookies)} cookies for {domain}")
            
            # Save cookies to file for inspection
            with open(f'cookies_{domain}.txt', 'w') as f:
                for cookie in cookies:
                    f.write(f"{cookie['name']} = {cookie['value']}\n")
            
            # Check for Cloudflare cookies
            cf_cookies = [cookie for cookie in cookies if cookie['name'] in ['__cf_bm', 'cf_clearance']]
            if cf_cookies:
                log.info(f"BROWSER: Found {len(cf_cookies)} Cloudflare cookies")
                for cookie in cf_cookies:
                    log.info(f"BROWSER: Cloudflare cookie: {cookie['name']}")
            
            # Get updated page source
            log.info(f"BROWSER: Getting page source for {domain}")
            page_source = await driver.page_source
            
            # Save page source for debugging
            with open(f'source_{domain}.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
            log.info(f"BROWSER: Saved page source to source_{domain}.html")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Look for __VIEWSTATE in the form
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            if viewstate:
                vs_token = viewstate.get('value')
                self.tokens[domain] = vs_token
                log.info(f"BROWSER: Successfully retrieved __VIEWSTATE token for {domain} (first 50 chars): {vs_token[:50]}...")
                
                # Save viewstate to file for inspection
                with open(f'viewstate_{domain}.txt', 'w') as f:
                    f.write(vs_token)
            else:
                log.warning(f"BROWSER: No __VIEWSTATE found in form for {domain}")
                # Check for other form tokens that might be used
                all_inputs = soup.find_all('input', {'type': 'hidden'})
                log.info(f"BROWSER: Found {len(all_inputs)} hidden inputs")
                
                with open(f'hidden_inputs_{domain}.txt', 'w') as f:
                    for inp in all_inputs:
                        input_name = inp.get('name', 'NO_NAME')
                        input_value = inp.get('value', 'NO_VALUE')
                        log.info(f"BROWSER: Hidden input: {input_name} = {input_value[:30] if input_value else 'None'}")
                        f.write(f"{input_name} = {input_value}\n")
            
            # For cloudflare sites or complex forms, try direct form submission
            if is_cloudflare or not viewstate:
                log.info(f"BROWSER: Cloudflare site or complex form detected, trying direct form submission")
                
                # Extract form fields for later use
                form_data = {}
                for inp in soup.find_all('input'):
                    name = inp.get('name')
                    if name:
                        form_data[name] = inp.get('value', '')
                
                self.form_data[domain] = form_data
                
                # Identify date fields
                date_start_field = None
                date_end_field = None
                date_type_field = None
                
                # Common field names
                start_fields = ['dateStart', 'ctl00$Main$dateStart', 'startdate', 'datefrom']
                end_fields = ['dateEnd', 'ctl00$Main$dateEnd', 'enddate', 'dateto']
                type_fields = ['cboSelectDateValue', 'ctl00$Main$cboSelectDateValue', 'datetype']
                
                # Find matching fields in the form
                for field in start_fields:
                    if soup.find('input', {'name': field}) or soup.find('select', {'name': field}):
                        date_start_field = field
                        break
                
                for field in end_fields:
                    if soup.find('input', {'name': field}) or soup.find('select', {'name': field}):
                        date_end_field = field
                        break
                
                for field in type_fields:
                    if soup.find('input', {'name': field}) or soup.find('select', {'name': field}):
                        date_type_field = field
                        break
                
                # Create JavaScript for direct form submission
                if date_start_field and date_end_field:
                    date_from = '15-02-2025'  # Use your actual date parameters
                    date_to = '21-02-2025'
                    
                    script = f"""
                    // Set date range
                    var startField = document.querySelector('[name="{date_start_field}"]');
                    var endField = document.querySelector('[name="{date_end_field}"]');
                    
                    if (startField) startField.value = '{date_from}';
                    if (endField) endField.value = '{date_to}';
                    
                    // Set date type if available
                    var typeField = document.querySelector('[name="{date_type_field}"]');
                    if (typeField) typeField.value = 'DATE_DECISION';
                    
                    // Check radio button for date range if present
                    var rangeRadio = document.querySelector('[value="rbRange"], [id="rbRange"]');
                    if (rangeRadio) rangeRadio.checked = true;
                    
                    // Find submit button
                    var submitBtn = document.querySelector('[value="Search"], [name*="Search"], [id*="Search"]');
                    if (submitBtn) {{
                        submitBtn.click();
                    }} else {{
                        // If no button found, just submit the form
                        document.forms[0].submit();
                    }}
                    """
                    
                    log.info(f"BROWSER: Executing form submission script")
                    try:
                        await driver.execute_script(script)
                        log.info(f"BROWSER: Form submitted via JavaScript")
                        
                        # Wait for results page
                        await asyncio.sleep(5)
                        
                        # Get the results URL
                        results_url = await driver.current_url
                        log.info(f"BROWSER: Results URL: {results_url}")
                        self.special_urls[domain] = results_url
                        
                        # Take another screenshot
                        await driver.save_screenshot(f'screenshot_results_{domain}.png')
                        
                        # Get updated cookies
                        cookies = await driver.get_cookies()
                        cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                        self.cookies[domain] = cookie_dict
                        
                        # Save results page
                        page_source = await driver.page_source
                        with open(f'results_{domain}.html', 'w', encoding='utf-8') as f:
                            f.write(page_source)
                    except Exception as e:
                        log.error(f"BROWSER: Error executing JavaScript: {e}")
            
            log.info(f"BROWSER: Closing browser for {domain}")
            await driver.quit()
            
            vs_token = self.tokens.get(domain)
            return vs_token, cookie_dict
                    
        except Exception as e:
            log.error(f"BROWSER: Error getting token for {url}: {e}", exc_info=True)
            # Save the error details to a file
            with open(f'browser_error_{domain}.txt', 'w') as f:
                f.write(f"Error at {datetime.now().isoformat()}: {str(e)}\n")
                f.write(traceback.format_exc())
            return None, None
        finally:
            # Make sure the browser is closed
            try:
                if 'driver' in locals() and driver:
                    log.info(f"BROWSER: Ensuring browser is closed for {domain}")
                    await driver.quit()
            except Exception as e:
                log.error(f"BROWSER: Error closing browser: {e}")

class AspxSel(scrapy.Spider):
    name = 'aspx_sel_spider2'
    allowed_domains = []  # Will be populated dynamically
    start_urls = ASPX_SEARCH_URLS
    
    # Date variables for search
    date_from = '15-02-2025'
    date_to = '21-02-2025'

    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 5,
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 3,
        'RETRY_DELAY': 5,
        'FEEDS': {
            'aspx_search_results.json': {
                'format': 'json',
                'overwrite': True
            }
        },
        'DOWNLOAD_TIMEOUT': 60,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
        'HTTPERROR_ALLOWED_CODES': [403, 404, 500, 502, 503, 504],
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
        },
        'ROBOTSTXT_OBEY': False,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'LOG_LEVEL': 'INFO'
    }

    def __init__(self, date_from=None, date_to=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate allowed_domains from start_urls
        self.allowed_domains = [get_domain(url) for url in self.start_urls]
        
        # Allow date override from command line
        if date_from:
            self.date_from = date_from
        if date_to:
            self.date_to = date_to
            
        # Initialize viewstate manager
        self.vs_manager = ViewstateManager()
        
        # Storage for collected tokens
        self.collected_data = {}
        
        log.info(f"Spider initialized with {len(self.start_urls)} URLs to process")
        log.info(f"Date range: {self.date_from} to {self.date_to}")

    def start_requests(self):
        """Start with the first URL to begin the chain"""
        if not self.start_urls:
            log.error("No start URLs provided!")
            return
            
        # Process URLs sequentially - start with the first one
        url = self.start_urls[0]
        log.info(f"Starting with URL: {url}")
        yield Request(
            url=url, 
            callback=self.prepare_token_and_request,
            meta={
                'url_index': 0,
                'dont_redirect': True, 
                'handle_httpstatus_list': [301, 302, 403, 500]
            },
            dont_filter=True
        )

    def prepare_token_and_request(self, response):
        """Use twisted.internet.threads to run async code safely from Scrapy"""
        current_index = response.meta.get('url_index', 0)
        current_url = self.start_urls[current_index]
        domain = get_domain(current_url)
        
        log.info(f"Preparing token for {current_url} (index: {current_index})")
        
        # Use deferred to run async code
        d = threads.deferToThread(self._run_async_token_fetch, current_url)
        d.addCallback(self._handle_token_result, response, current_url, domain, current_index)
        d.addErrback(self._handle_token_error, current_url, domain, current_index)
        return d
        
    def _run_async_token_fetch(self, url):
        """Helper to run async code in a thread"""
        log.info(f"Starting async token fetch for {url}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.vs_manager.get_token_for_url(url))
            log.info(f"Async token fetch completed for {url}")
            return result
        except Exception as e:
            log.error(f"Error in async token fetch for {url}: {e}", exc_info=True)
            raise
        finally:
            loop.close()
            
    def _handle_token_error(self, failure, url, domain, current_index):
        """Handle errors during token fetching"""
        log.error(f"Failed to fetch token for {url}: {failure.value}")
        
        requests = []
        
        # Try to continue with the next URL if possible
        if current_index + 1 < len(self.start_urls):
            next_url = self.start_urls[current_index + 1]
            log.info(f"Skipping problematic URL and moving to next: {next_url}")
            requests.append(
                Request(
                    url=next_url,
                    callback=self.prepare_token_and_request,
                    meta={
                        'url_index': current_index + 1, 
                        'dont_redirect': True, 
                        'handle_httpstatus_list': [301, 302, 403, 500]
                    },
                    dont_filter=True
                )
            )
        
        return requests
            
    def _handle_token_result(self, result, response, url, domain, current_index):
        """Process the token fetch result and schedule the form submission"""
        viewstate, cookies = result
        
        self.collected_data[domain] = {
            'viewstate': viewstate,
            'cookies': cookies,
            'base_url': url
        }
        
        if viewstate:
            log.info(f"Successfully collected viewstate for {domain} (length: {len(viewstate)})")
        else:
            log.warning(f"No viewstate collected for {domain}")
            
        if cookies:
            log.info(f"Successfully collected {len(cookies)} cookies for {domain}")
        else:
            log.warning(f"No cookies collected for {domain}")
        
        requests = []
        
        # Check if we have a special URL (for Cloudflare sites)
        special_url = self.vs_manager.special_urls.get(domain)
        
        if special_url:
            log.info(f"Using special results URL for {domain}: {special_url}")
            requests.append(
                Request(
                    url=special_url,
                    callback=self.parse_results,
                    cookies=cookies,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-GB,en;q=0.5',
                        'Referer': url,
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'same-origin',
                    },
                    meta={'base_url': url, 'domain': domain},
                    dont_filter=True,
                    errback=self.handle_error
                )
            )
        else:
            # Standard form submission
            if viewstate:
                # Get form data for this domain
                form_data = self.vs_manager.form_data.get(domain, {})
                
                # Start with basic form data
                submit_data = {
                    "__VIEWSTATE": viewstate,
                }
                
                # Handle different sites differently
                if 'blackburn' in domain:
                    # Blackburn-specific
                    submit_data.update({
                        "__EVENTTARGET": "ctl00$Main$csbtnSearch",
                        "__EVENTARGUMENT": "",
                        'ctl00$Main$dateStart': self.date_from, 
                        'ctl00$Main$dateEnd': self.date_to, 
                        'ctl00$Main$cboSelectDateValue': 'DATE_DECISION',
                        'ctl00$Main$rbGroup': 'rbRange'
                    })
                else:
                    # Generic form submission
                    submit_data.update({
                        'dateStart': self.date_from, 
                        'dateEnd': self.date_to, 
                        'cboSelectDateValue': 'DATE_DECISION',
                        'csbtnSearch': 'Search',
                        'rbGroup': 'rbRange'
                    })
                
                # Add any other form fields we found
                for name, value in form_data.items():
                    if name not in submit_data and name != "__VIEWSTATE":
                        submit_data[name] = value
                
                log.info(f"Submitting form with viewstate for {url}")
                requests.append(
                    FormRequest(
                        url=url,
                        formdata=submit_data,
                        cookies=cookies,
                        callback=self.parse_results,
                        meta={'base_url': url, 'domain': domain},
                        dont_filter=True,
                        errback=self.handle_error
                    )
                )
            else:
                # Try handle_no_viewstate for sites without viewstate
                log.info(f"No viewstate found, trying simple form for {url}")
                requests.append(
                    Request(
                        url=url,
                        callback=self.handle_no_viewstate,
                        cookies=cookies,
                        meta={'base_url': url, 'domain': domain},
                        dont_filter=True,
                        errback=self.handle_error
                    )
                )
        
        # Chain to the next URL if there are more
        if current_index + 1 < len(self.start_urls):
            next_url = self.start_urls[current_index + 1]
            log.info(f"Scheduling next URL: {next_url}")
            requests.append(
                Request(
                    url=next_url,
                    callback=self.prepare_token_and_request,
                    meta={
                        'url_index': current_index + 1, 
                        'dont_redirect': True, 
                        'handle_httpstatus_list': [301, 302, 403, 500]
                    },
                    dont_filter=True
                )
            )
            
        return requests

    def handle_no_viewstate(self, response):
        """Handle sites that don't use viewstate or where we couldn't extract it"""
        base_url = response.meta.get('base_url')
        domain = response.meta.get('domain')
        
        # Try to identify the search form
        form = response.css('form').get()
        if not form:
            log.error(f"No form found on {base_url}")
            return
        
        # Get all form inputs including non-hidden ones
        form_inputs = {}
        for inp in response.css('form input'):
            name = inp.css('::attr(name)').get()
            value = inp.css('::attr(value)').get('')
            if name:
                form_inputs[name] = value
        
        # Add our search parameters - try both naming conventions
        search_params = {
            'dateStart': self.date_from, 
            'dateEnd': self.date_to, 
            'ctl00$Main$dateStart': self.date_from,
            'ctl00$Main$dateEnd': self.date_to,
            'cboSelectDateValue': 'DATE_DECISION',
            'ctl00$Main$cboSelectDateValue': 'DATE_DECISION',
            'csbtnSearch': 'Search',
            'ctl00$Main$csbtnSearch': 'Search',
            'rbGroup': 'rbRange',
            'ctl00$Main$rbGroup': 'rbRange'
        }
        
        # Update form inputs with our search params
        form_inputs.update(search_params)
        
        # Submit the form
        yield FormRequest.from_response(
            response,
            formdata=form_inputs,
            callback=self.parse_results,
            meta={'base_url': base_url, 'domain': domain},
            errback=self.handle_error
        )

    def parse_results(self, response):
        """Parse search results and extract links"""
        log.info(f"Parsing results from {response.url}")
        log.info(f"Status: {response.status}")
        
        # Check for error pages
        if response.status in [403, 404, 500, 502, 503, 504]:
            log.error(f"Received error status {response.status} for {response.url}")
            return
        
        # Save the response for debugging
        domain = response.meta.get('domain', get_domain(response.url))
        with open(f'results_page_{domain}.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        # Try different selectors for links, as the sites might have different structures
        links = []
        
        # Common selectors for application links
        link_selectors = [
            '//a[@class="data_text"]/@href',
            'a[href*="Application"]::attr(href)',
            'table.dataview a::attr(href)',
            '//a[contains(@href, "application") or contains(@href, "Application")]/@href',
            'a[href*="Details.aspx"]::attr(href)',
            'table.display_table tr td a::attr(href)',
            '//td/a[contains(@href, "Details")]/@href',
            '//a[contains(@href, "ValidateCfChallenge")]/@href'
        ]
        
        # Try each selector until we find links
        for selector in link_selectors:
            if selector.startswith('//'):
                # XPath selector
                found_links = response.xpath(selector).getall()
            else:
                # CSS selector
                found_links = response.css(selector).getall()
            
            if found_links:
                links.extend(found_links)
                log.info(f"Found {len(found_links)} links using selector: {selector}")
        
        # Remove duplicates
        links = list(set(links))
        
        if not links:
            log.warning(f"No links found on {response.url}")
            log.info(f"Page title: {response.css('title::text').get()}")
            return
        
        log.info(f"Found {len(links)} application links")
        
        # Process each link
        for link in links:
            absolute_url = response.urljoin(link)
            log.info(f"Processing link: {absolute_url}")
            
            yield Request(
                url=absolute_url,
                callback=self.parse_plan_apps,
                cookies=response.request.cookies,
                headers=getattr(response.request, 'headers', {}),
                meta={
                    "domain": domain,
                    "base_url": response.meta.get('base_url'),
                    "handle_httpstatus_list": [403, 404, 500, 502, 503, 504],
                    "download_timeout": 30,
                    "max_retry_times": 3
                },
                dont_filter=True,
                errback=self.handle_error
            )
        
        # Check for pagination
        next_page = None
        pagination_selectors = [
            'a:contains("Next")::attr(href)',
            '//a[contains(text(), "Next") or contains(text(), "Next Page")]/@href',
            'a.next::attr(href)',
            'a[href*="page="]::attr(href)',
            '//a[contains(@href, "page=") and contains(text(), "Next")]/@href'
        ]
        
        for selector in pagination_selectors:
            if selector.startswith('//'):
                # XPath selector
                found_next = response.xpath(selector).get()
            else:
                # CSS selector
                found_next = response.css(selector).get()
            
            if found_next:
                next_page = found_next
                log.info(f"Found next page using selector: {selector}")
                break
        
        if next_page:
            next_url = response.urljoin(next_page)
            log.info(f"Found next page: {next_url}")
            yield Request(
                url=next_url,
                callback=self.parse_results,
                cookies=response.request.cookies,
                headers=getattr(response.request, 'headers', {}),
                meta=response.meta,
                dont_filter=True,
                errback=self.handle_error
            )

    def handle_error(self, failure):
        """Handle request failures"""
        request = failure.request
        url = request.url
        domain = get_domain(url)
        log.error(f"Request failed for {domain}: {url}")
        log.error(f"Error: {failure.value}")
        
        # Log additional details if available
        if hasattr(failure.value, 'response'):
            log.error(f"Response status: {failure.value.response.status}")
            
            # Save error response
            with open(f'error_{domain}.html', 'w', encoding='utf-8') as f:
                f.write(failure.value.response.text)
        
        # Try to continue with the next URL if this was a start_url
        if url in self.start_urls:
            current_index = self.start_urls.index(url)
            if current_index + 1 < len(self.start_urls):
                next_url = self.start_urls[current_index + 1]
                log.info(f"Moving to next URL after error: {next_url}")
                return Request(
                    url=next_url,
                    callback=self.prepare_token_and_request,
                    meta={
                        'url_index': current_index + 1, 
                        'dont_redirect': True, 
                        'handle_httpstatus_list': [301, 302, 403, 500]
                    },
                    dont_filter=True
                )

    def parse_plan_apps(self, response):
        """Parse individual application details"""
        domain = response.meta.get('domain', get_domain(response.url))
        log.info(f"Parsing application details from {response.url} (domain: {domain})")
        
        # Save the details page for inspection
        with open(f'details_{domain}_{response.url.split("/")[-1]}.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        
        loader = ItemLoader(item=PlanningApplicationItem(), response=response)
        
        try:
            # Add the domain and URL info first
            loader.add_value('council_name', domain)
            loader.add_value('council_url', response.meta.get('base_url'))
            loader.add_value('application_url', response.url)
            
            # Different sites use different structures, so we'll try multiple approaches
            
            # Base XPaths with improved section detection
            details_selectors = [
                '//div[contains(@class,"dataview")][.//h1[contains(., "Application Details")]]',
                '//div[contains(@class,"col-md")][.//h3[contains(., "Application Details")]]',
                '//table[contains(@class,"dataview")]',
                '//div[@id="app_details"]',
                '//table[contains(@class, "display_table")]',
                '//div[contains(@class, "details")]',
                '//div[@id="details"]'
            ]
            
            # Try each selector until we find one that works
            details_base = None
            for selector in details_selectors:
                if response.xpath(selector).get():
                    details_base = selector
                    log.info(f"Found details using selector: {selector}")
                    break
            
            if not details_base:
                log.warning(f"Could not find application details section on {response.url}")
                # Try a more generic approach
                details_base = '//body'
            
            # Generic field extraction with error handling
            field_mappings = {
                'application_reference': ['Application Number', 'Reference', 'App Number', 'Planning Reference', 'Application Ref'],
                'site_address': ['Site Address', 'Address', 'Location', 'Property', 'Site Location'],
                'application_type': ['Application Type', 'Type', 'Application Category'],
                'description': ['Proposal', 'Description', 'Development', 'Details', 'Proposal Description'],
                'status': ['Current Status', 'Status', 'Decision', 'Application Status'],
                'applicant_name': ['Applicant', 'Applicant Name', 'Applicant Details'],
                'agent_name': ['Agent', 'Agent Name', 'Agent Details', 'Agent Company'],
                'ward': ['Wards', 'Ward', 'Electoral Division', 'Area'],
                'parish': ['Parishes', 'Parish', 'Town'],
                'case_officer_name': ['Planning Officer', 'Case Officer', 'Officer', 'Contact Officer'],
                'case_officer_telephone': ['Case Officer / Tel', 'Officer Tel', 'Telephone', 'Contact Number'],
                'determination_level': ['Determination Level', 'Decision Level', 'Decided By'],
                'development_type': ['Development Type', 'Type of Development', 'Category'],
                'location_coordinates': ['Location Co ordinates', 'Coordinates', 'Grid Ref', 'Map Reference'],
                'os_mapsheet': ['OS Mapsheet', 'Map Sheet', 'OS Map'],
                'appeal_submitted': ['Appeal Submitted?', 'Appeal Submitted', 'Appeal', 'Appeal Status'],
                'appeal_decision': ['Appeal Decision', 'Appeal Outcome', 'Appeal Result'],
                'division': ['Division', 'Area', 'District'],
                'existing_land_use': ['Existing Land Use', 'Current Use', 'Present Use'],
                'proposed_land_use': ['Proposed Land Use', 'Proposed Use', 'Future Use']
            }
            
            # Try to extract each field using various selectors
            for field_name, labels in field_mappings.items():
                for label in labels:
                    try:
                        # Try multiple xpath patterns
                        values = []
                        patterns = [
                            f'{details_base}//div[.//span[contains(., "{label}")]]/text()',
                            f'{details_base}//tr[td[contains(., "{label}")]]/td[2]//text()',
                            f'//td[contains(text(), "{label}")]/following-sibling::td[1]//text()',
                            f'//th[contains(text(), "{label}")]/following-sibling::td[1]//text()',
                            f'//div[contains(text(), "{label}")]/following-sibling::div[1]//text()',
                            f'//span[contains(text(), "{label}")]/following-sibling::span[1]//text()',
                            f'//label[contains(text(), "{label}")]/following-sibling::*[1]//text()'
                        ]
                        
                        for pattern in patterns:
                            extracted = response.xpath(pattern).getall()
                            if extracted:
                                values.extend(extracted)
                                log.info(f"Found {field_name} using pattern: {pattern}")
                                break
                        
                        if values:
                            # Clean up the values
                            cleaned = [v.strip() for v in values if v.strip()]
                            if cleaned:
                                loader.add_value(field_name, " ".join(cleaned))
                                break  # Found a value, move to next field
                    except KeyError:
                        continue
                    except Exception as e:
                        log.warning(f"Error extracting {field_name} using {label} from {response.url}: {str(e)}")
            
            # Try to find dates
            date_fields = {
                'application_registered_date': ['Application Registered', 'Registration Date', 'Date Received', 'Receipt Date', 'Received'],
                'comments_until_date': ['Comments Until', 'Consultation End', 'Expiry Date', 'Consultation Expiry', 'Comment By'],
                'decision_issued_date': ['Decision Issued', 'Decision Date', 'Date of Decision', 'Decided On']
            }
            
            for field_name, labels in date_fields.items():
                for label in labels:
                    try:
                        patterns = [
                            f'//div[contains(., "{label}")]/text()',
                            f'//tr[td[contains(., "{label}")]]/td[2]//text()',
                            f'//td[contains(text(), "{label}")]/following-sibling::td[1]//text()',
                            f'//th[contains(text(), "{label}")]/following-sibling::td[1]//text()',
                            f'//div[contains(text(), "{label}")]/following-sibling::div[1]//text()',
                            f'//span[contains(text(), "{label}")]/following-sibling::span[1]//text()',
                            f'//label[contains(text(), "{label}")]/following-sibling::*[1]//text()'
                        ]
                        
                        for pattern in patterns:
                            date_value = response.xpath(pattern).get()
                            if date_value and date_value.strip():
                                loader.add_value(field_name, date_value.strip())
                                log.info(f"Found {field_name}: {date_value.strip()}")
                                break
                    except Exception as e:
                        log.warning(f"Error extracting {field_name} from {response.url}: {str(e)}")

            # Return the loaded item
            return loader.load_item()
            
        except Exception as e:
            log.error(f"Critical error processing {response.url}: {str(e)}", exc_info=True)
            return None