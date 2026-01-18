"""
NECSWS ES/Presentation Spider - scrapes UK planning portals using the NECSWS framework.

This spider handles JavaScript-heavy portals requiring Playwright for form interaction.
Supports: Hounslow (London borough)

Flow:
1. Use Playwright to load portal and wait for JS initialization
2. Dynamically discover form elements (date inputs, search button)
3. Fill date range and submit search
4. Parse search results for application links
5. Follow each application to details page
6. Extract metadata and documents
7. Yield application and document items
"""

import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy.http import HtmlResponse
from scrapy_playwright.page import PageMethod

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_necsws_urls


def _get_playwright_proxy_config():
    """Get proxy config for Playwright from environment."""
    proxy_url = os.environ.get("PROXY_URL")
    if not proxy_url:
        return None

    parsed = urlparse(proxy_url)

    if parsed.username and parsed.password:
        return {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username,
            "password": parsed.password,
        }
    else:
        return {"server": proxy_url}


class NECSWSSpider(scrapy.Spider):
    """
    Spider for NECSWS ES/Presentation-based planning portals.

    Handles JavaScript-heavy forms and date-based searches.

    Usage:
        scrapy crawl necsws -a region=london -a days_back=30
        scrapy crawl necsws -a council=hounslow -a days_back=30
        scrapy crawl necsws -a council=hounslow -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "necsws"

    # Form element selectors for dynamic discovery
    DATE_FROM_SELECTORS = [
        'input[name*="DateFrom" i]',
        'input[name*="datefrom" i]',
        'input[id*="DateFrom" i]',
        'input[id*="datefrom" i]',
        'input[placeholder*="from" i]',
        'input[aria-label*="from" i]',
        "#txtDateFrom",
        "#DateFrom",
        "#dateFrom",
        'input[name*="StartDate" i]',
        'input[id*="StartDate" i]',
        'input[name*="ReceivedFrom" i]',
        'input[id*="ReceivedFrom" i]',
    ]

    DATE_TO_SELECTORS = [
        'input[name*="DateTo" i]',
        'input[name*="dateto" i]',
        'input[id*="DateTo" i]',
        'input[id*="dateto" i]',
        'input[placeholder*="to" i]',
        'input[aria-label*="to" i]',
        "#txtDateTo",
        "#DateTo",
        "#dateTo",
        'input[name*="EndDate" i]',
        'input[id*="EndDate" i]',
        'input[name*="ReceivedTo" i]',
        'input[id*="ReceivedTo" i]',
    ]

    SEARCH_BUTTON_SELECTORS = [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Search")',
        'input[value*="Search" i]',
        'button:has-text("search")',
        "#btnSearch",
        "#searchButton",
        ".search-button",
        'a:has-text("Search")',
        '[onclick*="search" i]',
    ]

    @classmethod
    def _build_custom_settings(cls):
        """Build custom settings with proxy config."""
        proxy_config = _get_playwright_proxy_config()

        settings = {
            # Playwright settings for browser-based scraping
            "DOWNLOAD_HANDLERS": {
                "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
                "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            },
            "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
            "PLAYWRIGHT_BROWSER_TYPE": "chromium",
            "PLAYWRIGHT_LAUNCH_OPTIONS": {
                "headless": True,
            },
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,
            # Conservative rate limiting for council portals
            "CONCURRENT_REQUESTS": 1,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
            "DOWNLOAD_DELAY": 3.0,
            "COOKIES_ENABLED": True,
            "RETRY_ENABLED": True,
            "RETRY_TIMES": 3,
            "AUTOTHROTTLE_ENABLED": True,
            "AUTOTHROTTLE_START_DELAY": 3.0,
            "AUTOTHROTTLE_MAX_DELAY": 15.0,
            "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
            "DOWNLOAD_TIMEOUT": 180,
            # Handle common error codes
            "HTTPERROR_ALLOWED_CODES": [403, 404],
            # Disable Scrapy's proxy middleware for Playwright
            "DOWNLOADER_MIDDLEWARES": {
                "planning_scraper.middlewares.proxy.ProxyMiddleware": None,
            },
        }

        # Configure proxy at Playwright context level if available
        if proxy_config:
            settings["PLAYWRIGHT_CONTEXTS"] = {
                "default": {
                    "proxy": proxy_config,
                }
            }

        return settings

    custom_settings = _build_custom_settings.__func__(None)

    def __init__(
        self,
        days_back: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        region: Optional[str] = None,
        council: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Store parameters
        self.region = region
        self.council = council

        # Get URLs based on region/council filter
        self.portal_urls = get_necsws_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No NECSWS portals found for region='{region}', council='{council}'. "
                "Valid councils: hounslow"
            )

        # Calculate date range
        if start_date and end_date:
            self.start_date = start_date
            self.end_date = end_date
        else:
            end = datetime.now()
            start = end - timedelta(days=int(days_back))
            self.start_date = start.strftime("%d/%m/%Y")
            self.end_date = end.strftime("%d/%m/%Y")

        # Build allowed domains from URLs
        self.allowed_domains = list(
            {urlparse(config["url"]).netloc.split(":")[0] for config in self.portal_urls.values()}
        )

        # Stats
        self.stats = {
            "councils_processed": 0,
            "applications_found": 0,
            "documents_found": 0,
        }

        # Log startup configuration
        self._log_startup_config()

    def _log_startup_config(self):
        """Log clear startup configuration."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("NECSWS SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 3.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests for each NECSWS portal."""
        for council_name, config in self.portal_urls.items():
            self.logger.info(f"Starting scrape for council: {council_name}")

            yield scrapy.Request(
                url=config["url"],
                callback=self.parse_search_page,
                cb_kwargs={"council_name": council_name, "config": config},
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("wait_for_timeout", 5000),  # Extra wait for JS init
                    ],
                },
            )

    async def parse_search_page(self, response, council_name: str, config: Dict[str, str]):
        """
        Parse the search page and submit a date-based search using Playwright.
        """
        page = response.meta.get("playwright_page")

        if response.status == 403:
            self.logger.warning(f"403 Forbidden for {council_name} search page")
            if page:
                await page.close()
            return

        self.logger.info(f"Parsing search page for {council_name} (status: {response.status})")

        # Close the Scrapy-Playwright page, we'll use our own browser for form submission
        if page:
            await page.close()

        # Use a fresh Playwright browser for form submission with full control
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                proxy_config = _get_playwright_proxy_config()
                browser = await p.chromium.launch(headless=True)

                # Create context with proxy if configured
                if proxy_config:
                    context = await browser.new_context(proxy=proxy_config)
                    fresh_page = await context.new_page()
                else:
                    fresh_page = await browser.new_page()

                # Navigate to search page
                self.logger.info(f"Navigating to {config['url']}")
                await fresh_page.goto(config["url"], wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)  # Wait for JS to fully initialize

                # Accept cookies if there's a cookie banner
                await self._accept_cookies(fresh_page)

                # Find and fill date fields dynamically
                date_from_found = await self._find_and_fill_date_field(
                    fresh_page, self.DATE_FROM_SELECTORS, self.start_date, "date from"
                )
                date_to_found = await self._find_and_fill_date_field(
                    fresh_page, self.DATE_TO_SELECTORS, self.end_date, "date to"
                )

                if not date_from_found or not date_to_found:
                    self.logger.warning(
                        f"Could not find date fields for {council_name}. "
                        "Attempting search without date filter."
                    )

                # Find and click search button
                search_clicked = await self._find_and_click_search(fresh_page)

                if not search_clicked:
                    self.logger.error(f"Could not find search button for {council_name}")
                    # Try to continue anyway - page might have default results

                # Wait for results to load
                await asyncio.sleep(5)
                await fresh_page.wait_for_load_state("networkidle")

                # Get results page content
                results_url = fresh_page.url
                content = await fresh_page.content()

                self.logger.info(f"Results URL: {results_url}")

                await browser.close()

            # Parse results
            results_response = HtmlResponse(
                url=results_url,
                body=content.encode("utf-8"),
                encoding="utf-8",
            )

            # Yield results from this response
            async for item in self._parse_search_results(
                results_response, council_name, config
            ):
                yield item

        except Exception as e:
            self.logger.error(f"Error processing search for {council_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    async def _accept_cookies(self, page):
        """Try to accept cookies if there's a cookie banner."""
        cookie_selectors = [
            'button:has-text("Accept")',
            'button:has-text("accept")',
            'button:has-text("Accept All")',
            'a:has-text("Accept")',
            "#accept-cookies",
            ".cookie-accept",
            '[data-action="accept"]',
        ]

        for selector in cookie_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    self.logger.debug("Accepted cookies")
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue

    async def _find_and_fill_date_field(
        self, page, selectors: List[str], date_value: str, field_name: str
    ) -> bool:
        """Try multiple selectors to find and fill a date field."""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    # Clear existing value and fill
                    await element.click()
                    await element.fill("")
                    await element.fill(date_value)
                    self.logger.info(f"Filled {field_name} with {date_value} using selector: {selector}")
                    return True
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed for {field_name}: {e}")
                continue

        self.logger.warning(f"Could not find {field_name} field")
        return False

    async def _find_and_click_search(self, page) -> bool:
        """Try multiple selectors to find and click the search button."""
        for selector in self.SEARCH_BUTTON_SELECTORS:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    self.logger.info(f"Clicked search button using selector: {selector}")
                    return True
            except Exception as e:
                self.logger.debug(f"Search selector {selector} failed: {e}")
                continue

        self.logger.warning("Could not find search button")
        return False

    async def _parse_search_results(
        self, response, council_name: str, config: Dict[str, str]
    ):
        """Parse search results and follow application links."""
        self.logger.info(f"Parsing search results for {council_name}")
        self.stats["councils_processed"] += 1

        # Look for application links - NECSWS portals use various patterns
        app_links = self._extract_application_links(response)

        self.logger.info(f"Found {len(app_links)} applications for {council_name}")

        if not app_links:
            self.logger.warning(f"No application links found for {council_name}")
            self.logger.debug(f"Page title: {response.css('title::text').get()}")
            # Log a snippet to help debug
            content_preview = response.text[:2000] if response.text else "No content"
            self.logger.debug(f"Page content preview: {content_preview}")
            return

        # Follow each application link
        for link_info in app_links:
            link = link_info["url"]
            app_url = urljoin(response.url, link)

            # Skip if this is the same page
            if app_url == response.url:
                continue

            yield scrapy.Request(
                url=app_url,
                callback=self.parse_application_details,
                cb_kwargs={
                    "council_name": council_name,
                    "config": config,
                    "app_ref_hint": link_info.get("ref"),
                },
                meta={
                    "council_name": council_name,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
                dont_filter=True,
            )

        # Check for pagination
        next_page = self._find_next_page_link(response)
        if next_page:
            self.logger.info(f"Following pagination for {council_name}")
            yield scrapy.Request(
                url=urljoin(response.url, next_page),
                callback=self._parse_search_results_page,
                cb_kwargs={"council_name": council_name, "config": config},
                meta={
                    "council_name": council_name,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                    ],
                },
                dont_filter=True,
            )

    def _extract_application_links(self, response) -> List[Dict[str, str]]:
        """Extract application links from search results."""
        links = []

        # Try various NECSWS-specific selectors
        selectors = [
            # Common NECSWS patterns
            'a[href*="ApplicationDetails"]',
            'a[href*="Details"]',
            'a[href*="View"]',
            # Table-based results
            'table tbody tr a',
            'table.results a',
            # List-based results
            '.application-link',
            '.search-result a',
            # Generic patterns
            'a[href*="Planning"]',
            'a[href*="Application"]',
        ]

        for selector in selectors:
            elements = response.css(selector)
            for el in elements:
                href = el.attrib.get("href", "")
                text = el.css("::text").get() or ""

                # Skip navigation/menu links
                if any(skip in href.lower() for skip in ["login", "register", "home", "help", "contact"]):
                    continue

                # Skip JavaScript-only links
                if href.startswith("javascript:") and "Application" not in href:
                    continue

                links.append({"url": href, "ref": text.strip()})

        # Deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in links:
            if link["url"] not in seen:
                seen.add(link["url"])
                unique_links.append(link)

        return unique_links

    def _find_next_page_link(self, response) -> Optional[str]:
        """Find the next page link for pagination."""
        next_selectors = [
            'a:has-text("Next")',
            'a:has-text("next")',
            'a.next::attr(href)',
            'a[rel="next"]::attr(href)',
            '.pagination a:has-text(">")',
            'a[title*="Next"]::attr(href)',
        ]

        for selector in next_selectors:
            if "::" in selector:
                link = response.css(selector).get()
            else:
                link = response.xpath(f'//{selector}/@href').get()

            if link:
                return link

        return None

    async def _parse_search_results_page(
        self, response, council_name: str, config: Dict[str, str]
    ):
        """Parse a paginated search results page."""
        page = response.meta.get("playwright_page")
        if page:
            await page.close()

        async for item in self._parse_search_results(response, council_name, config):
            yield item

    async def parse_application_details(
        self, response, council_name: str, config: Dict[str, str], app_ref_hint: Optional[str] = None
    ):
        """Parse application details page and extract metadata."""
        page = response.meta.get("playwright_page")

        if response.status in [403, 404]:
            self.logger.warning(f"{response.status} for application at {response.url}")
            if page:
                await page.close()
            return

        self.logger.debug(f"Parsing application details for {council_name}: {response.url}")
        self.stats["applications_found"] += 1

        if page:
            await page.close()

        # Create application item
        app_item = PlanningApplicationItem()

        # Extract application reference from page or use hint from search results
        app_ref = self._extract_application_reference(response) or app_ref_hint or "unknown"
        app_item["application_reference"] = app_ref
        app_item["application_url"] = response.url
        app_item["council_name"] = council_name

        # Extract metadata from detail page
        app_item["site_address"] = self._extract_field(
            response, ["Site Address", "Address", "Location", "Site Location"]
        )
        app_item["proposal"] = self._extract_field(
            response, ["Proposal", "Description", "Development Description", "Development"]
        )
        app_item["application_type"] = self._extract_field(
            response, ["Application Type", "Type", "Category", "Application Category"]
        )
        app_item["status"] = self._extract_field(
            response, ["Status", "Application Status", "Current Status"]
        )
        app_item["decision"] = self._extract_field(
            response, ["Decision", "Decision Type", "Decision Outcome"]
        )
        app_item["registration_date"] = self._extract_field(
            response, ["Registration Date", "Date Received", "Received", "Valid Date", "Date Valid"]
        )
        app_item["decision_date"] = self._extract_field(
            response, ["Decision Date", "Decision Issued", "Date Decided"]
        )
        app_item["applicant_name"] = self._extract_field(
            response, ["Applicant", "Applicant Name"]
        )
        app_item["agent_name"] = self._extract_field(
            response, ["Agent", "Agent Name", "Agent Details"]
        )
        app_item["ward"] = self._extract_field(
            response, ["Ward", "Electoral Ward", "Wards"]
        )
        app_item["parish"] = self._extract_field(
            response, ["Parish", "Parishes"]
        )
        app_item["case_officer"] = self._extract_field(
            response, ["Case Officer", "Planning Officer", "Officer"]
        )

        # Extract postcode from address
        if app_item.get("site_address"):
            app_item["postcode"] = self._extract_postcode(app_item["site_address"])

        # Internal tracking
        app_item["_portal_framework"] = "necsws"
        app_item["_scraped_at"] = datetime.utcnow().isoformat()

        yield app_item

        # Find and follow the documents tab/link
        docs_url = self._find_documents_link(response)

        if docs_url:
            self.logger.debug(f"Following documents link: {docs_url}")
            yield scrapy.Request(
                url=docs_url,
                callback=self.parse_documents_tab,
                cb_kwargs={"app_ref": app_ref, "council_name": council_name},
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                    ],
                },
                dont_filter=True,
            )
        else:
            self.logger.debug(f"No documents link found for {app_ref}, extracting from current page")
            # Try to extract documents from current page
            for item in self._extract_documents_from_page(response, app_ref, council_name):
                yield item

    def _extract_application_reference(self, response) -> Optional[str]:
        """Extract application reference from the page."""
        # Try various patterns
        selectors = [
            # Direct field extraction
            '//span[contains(@id, "ApplicationNumber")]/text()',
            '//span[contains(@id, "Reference")]/text()',
            '//td[contains(text(), "Reference")]/following-sibling::td/text()',
            '//td[contains(text(), "Application Number")]/following-sibling::td/text()',
            '//th[contains(text(), "Reference")]/following-sibling::td/text()',
            '//div[contains(text(), "Reference")]/following-sibling::div/text()',
            # NECSWS specific patterns
            '//div[span[contains(text(), "Reference")]]/text()',
            '//div[span[contains(text(), "Application Number")]]/text()',
            '//li[contains(@class, "ref")]//text()',
        ]

        for selector in selectors:
            values = response.xpath(selector).getall()
            for value in values:
                cleaned = value.strip()
                # Check if it looks like a reference (contains letters and numbers)
                if cleaned and re.search(r'[A-Z0-9]', cleaned, re.IGNORECASE):
                    if cleaned.lower() not in ["n/a", "none", "-", "", "reference", "application number"]:
                        return cleaned

        # Try to extract from URL
        url = response.url
        patterns = [
            r'ApplicationNumber=([^&]+)',
            r'Reference=([^&]+)',
            r'/([A-Z]+/\d+/\d+)',  # Common format like P/12345/2024
            r'/(\d{4}/\d+)',  # Format like 2024/12345
        ]

        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)

        # Try the generic field extraction
        ref = self._extract_field(response, ["Reference", "Application Reference", "Ref", "Application Number"])
        return ref

    def _extract_field(self, response, labels: List[str]) -> Optional[str]:
        """Extract a field value from a detail page by label."""
        for label in labels:
            # Various HTML structure patterns
            selectors = [
                # div/span structure
                f'//div[span[normalize-space()="{label}"]]/text()',
                f'//div[span[contains(text(), "{label}")]]/text()',
                # table structure
                f'//th[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//td[contains(text(), "{label}")]/following-sibling::td/text()',
                # label/value structure
                f'//label[contains(text(), "{label}")]/following-sibling::*/text()',
                f'//strong[contains(text(), "{label}")]/following-sibling::text()',
                f'//strong[contains(text(), "{label}")]/../text()',
                # Definition list
                f'//dt[contains(text(), "{label}")]/following-sibling::dd/text()',
                # NECSWS specific
                f'//li[contains(@class, "{label.lower().replace(" ", "-")}")]/span/text()',
                f'//*[contains(@data-field, "{label}")]//text()',
            ]

            for selector in selectors:
                values = response.xpath(selector).getall()
                for value in values:
                    cleaned = value.strip()
                    if cleaned and cleaned.lower() not in ["n/a", "none", "-", ""]:
                        # Skip if it's just the label itself
                        if cleaned.lower() != label.lower():
                            return cleaned

        return None

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract postcode from address string."""
        if not address:
            return None

        pattern = r'[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}'
        match = re.search(pattern, address.upper())
        return match.group(0) if match else None

    def _find_documents_link(self, response) -> Optional[str]:
        """Find the link to the documents tab/page."""
        selectors = [
            'a[href*="Documents"]::attr(href)',
            'a[href*="documents"]::attr(href)',
            'a[href*="Tab"]::attr(href)',
            'a:contains("Documents")::attr(href)',
            'a:contains("Related Documents")::attr(href)',
            'a:contains("View Documents")::attr(href)',
        ]

        for selector in selectors:
            links = response.css(selector).getall()
            if links:
                return urljoin(response.url, links[0])

        xpath_selectors = [
            '//a[contains(@href, "Documents")]/@href',
            '//a[contains(@href, "documents")]/@href',
            '//a[contains(text(), "Documents")]/@href',
            '//a[contains(text(), "Related Documents")]/@href',
            '//a[contains(text(), "View Documents")]/@href',
            '//li[contains(@class, "tab")]//a[contains(text(), "Document")]/@href',
        ]

        for selector in xpath_selectors:
            links = response.xpath(selector).getall()
            if links:
                return urljoin(response.url, links[0])

        return None

    async def parse_documents_tab(self, response, app_ref: str, council_name: str):
        """Parse the documents tab and extract document links."""
        page = response.meta.get("playwright_page")
        if page:
            await page.close()

        self.logger.debug(f"Parsing documents tab for {app_ref}")
        for item in self._extract_documents_from_page(response, app_ref, council_name):
            yield item

    def _extract_documents_from_page(self, response, app_ref: str, council_name: str):
        """Extract all documents from a page."""
        # Try various document container selectors
        doc_rows = (
            response.xpath("//table[contains(@class, 'documents')]//tr[position()>1]")
            or response.xpath("//table[@id='documents']//tr[position()>1]")
            or response.xpath("//div[contains(@class, 'documents')]//table//tr")
            or response.xpath("//table//tbody//tr[.//a[contains(@href, '.pdf')]]")
        )

        if doc_rows:
            self.logger.debug(f"Found {len(doc_rows)} document rows for {app_ref}")
            for row in doc_rows:
                item = self._extract_document_from_row(row, response, app_ref, council_name)
                if item:
                    yield item
        else:
            # Fallback: find all PDF/document links on the page
            yield from self._extract_pdf_links(response, app_ref, council_name)

    def _extract_document_from_row(
        self, row, response, app_ref: str, council_name: str
    ) -> Optional[DocumentItem]:
        """Extract document info from a table row."""
        doc_url = (
            row.xpath(".//a[contains(@href, '.pdf')]/@href").get()
            or row.xpath(".//a[contains(@href, 'ViewDocument')]/@href").get()
            or row.xpath(".//a[contains(@href, 'Download')]/@href").get()
            or row.xpath(".//a[contains(@href, 'download')]/@href").get()
            or row.xpath(".//a[contains(@href, 'Document')]/@href").get()
            or row.xpath(".//a/@href").get()
        )

        if not doc_url:
            return None

        doc_url = urljoin(response.url, doc_url)

        # Extract filename from link text or URL
        filename = (
            row.xpath(".//a/text()").get()
            or row.xpath(".//td[1]/text()").get()
            or self._extract_filename_from_url(doc_url)
        )

        if filename:
            filename = filename.strip()

        return self._create_document_item(
            doc_url, filename, response.url, app_ref, council_name
        )

    def _extract_pdf_links(self, response, app_ref: str, council_name: str):
        """Extract all PDF links from the page."""
        pdf_links = (
            response.xpath("//a[contains(@href, '.pdf')]/@href").getall()
            or response.xpath("//a[contains(@href, 'ViewDocument')]/@href").getall()
            or response.xpath("//a[contains(@href, 'Download')]/@href").getall()
        )

        self.logger.debug(f"Found {len(pdf_links)} PDF links for {app_ref}")

        for doc_url in pdf_links:
            doc_url = urljoin(response.url, doc_url)
            filename = self._extract_filename_from_url(doc_url)

            yield self._create_document_item(
                doc_url, filename, response.url, app_ref, council_name
            )

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import unquote
        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = path.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]
        return filename if filename else "document.pdf"

    def _create_document_item(
        self,
        doc_url: str,
        filename: str,
        source_url: str,
        app_ref: str,
        council_name: str,
    ) -> DocumentItem:
        """Create a DocumentItem with all required fields."""
        self.stats["documents_found"] += 1

        item = DocumentItem()
        item["document_url"] = doc_url
        item["source_url"] = source_url
        item["filename"] = filename or "document.pdf"
        item["application_reference"] = app_ref
        item["council_name"] = council_name
        item["_portal_framework"] = "necsws"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("NECSWS SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
