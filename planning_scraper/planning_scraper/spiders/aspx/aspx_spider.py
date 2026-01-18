"""
ASPX/Northgate Spider - scrapes UK planning portals using the Northgate ASPX framework.

This spider handles date-based searches across multiple ASPX portals.
Supports: Camden, Islington, Merton (London boroughs)

Flow:
1. GET search page to establish session and extract ASP.NET form tokens
2. POST search with date range
3. Parse search results for application links
4. Follow each application to details page
5. Extract metadata and follow to documents tab
6. Yield application and document items
"""

from datetime import datetime, timedelta
import os
from typing import Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy_playwright.page import PageMethod

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_aspx_urls


def _get_playwright_proxy_config():
    """Get proxy config for Playwright from environment."""
    proxy_url = os.environ.get("PROXY_URL")
    if not proxy_url:
        return None

    # Parse proxy URL: http://user:pass@host:port
    from urllib.parse import urlparse
    parsed = urlparse(proxy_url)

    if parsed.username and parsed.password:
        return {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username,
            "password": parsed.password,
        }
    else:
        return {"server": proxy_url}


class AspxSpider(scrapy.Spider):
    """
    Spider for ASPX/Northgate-based planning portals.

    Handles date-based searches and extracts planning applications
    and associated documents.

    Usage:
        scrapy crawl aspx -a region=london -a days_back=30
        scrapy crawl aspx -a council=islington -a days_back=30
        scrapy crawl aspx -a council=merton -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "aspx"

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
            "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 60000,
            # Conservative rate limiting for council portals
            "CONCURRENT_REQUESTS": 2,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
            "DOWNLOAD_DELAY": 2.0,
            "COOKIES_ENABLED": True,
            "RETRY_ENABLED": True,
            "RETRY_TIMES": 3,
            "AUTOTHROTTLE_ENABLED": True,
            "AUTOTHROTTLE_START_DELAY": 2.0,
            "AUTOTHROTTLE_MAX_DELAY": 10.0,
            "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
            "DOWNLOAD_TIMEOUT": 120,
            # Handle common error codes
            "HTTPERROR_ALLOWED_CODES": [403],
            # Disable Scrapy's proxy middleware for Playwright (we configure proxy at browser level)
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
        self.portal_urls = get_aspx_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No ASPX portals found for region='{region}', council='{council}'. "
                "Valid councils: camden, merton"
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
            {urlparse(url).netloc.split(":")[0] for url in self.portal_urls.values()}
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
        self.logger.info("ASPX SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 2.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests for each ASPX portal."""
        for council_name, url in self.portal_urls.items():
            self.logger.info(f"Starting scrape for council: {council_name}")

            yield scrapy.Request(
                url=url,
                callback=self.parse_search_page,
                cb_kwargs={"council_name": council_name, "base_url": url},
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "domcontentloaded"),
                        PageMethod("wait_for_timeout", 2000),
                    ],
                },
            )

    async def parse_search_page(self, response, council_name: str, base_url: str):
        """
        Parse the search page and submit a date-based search using Playwright.
        """
        page = response.meta.get("playwright_page")

        # Check for error responses
        if response.status == 403:
            self.logger.warning(f"403 Forbidden for {council_name} search page")
            if page:
                await page.close()
            return

        self.logger.info(f"Parsing search page for {council_name} (status: {response.status})")

        # Check if we have the ASP.NET form
        viewstate = response.css('input#__VIEWSTATE::attr(value)').get()
        if not viewstate:
            self.logger.error(f"Could not find __VIEWSTATE for {council_name}")
            if page:
                await page.close()
            return

        self.logger.info(f"Found form tokens for {council_name}")

        # Close the Scrapy-Playwright page, we'll use our own browser
        if page:
            await page.close()

        # Use a fresh Playwright browser for form submission
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as p:
                # Get proxy config for the browser
                proxy_config = _get_playwright_proxy_config()
                browser = await p.chromium.launch(headless=True)

                # Create context with proxy if configured
                if proxy_config:
                    context = await browser.new_context(proxy=proxy_config)
                    fresh_page = await context.new_page()
                else:
                    fresh_page = await browser.new_page()

                # Navigate to search page
                await fresh_page.goto(base_url)
                await fresh_page.wait_for_load_state("networkidle")

                # Fill and submit search form
                await fresh_page.click("#rbRange")
                await fresh_page.select_option("#cboSelectDateValue", "DATE_DECISION")
                await fresh_page.fill("#dateStart", self.start_date)
                await fresh_page.fill("#dateEnd", self.end_date)

                self.logger.info(f"Submitting search for {council_name}: {self.start_date} to {self.end_date}")

                # Click search and wait for results
                await fresh_page.click("#csbtnSearch")
                await fresh_page.wait_for_load_state("networkidle")

                import asyncio
                await asyncio.sleep(2)

                # Get the results
                results_url = fresh_page.url
                content = await fresh_page.content()

                self.logger.info(f"Results URL: {results_url}")

                await browser.close()

            # Parse results
            from scrapy.http import HtmlResponse
            results_response = HtmlResponse(
                url=results_url,
                body=content.encode('utf-8'),
                encoding='utf-8',
            )

            # Yield results from this response
            async for item in self._parse_search_results_from_response(
                results_response, council_name, base_url
            ):
                yield item

        except Exception as e:
            self.logger.error(f"Error submitting search form for {council_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def handle_playwright_error(self, failure):
        """Handle Playwright errors - try alternative selectors."""
        council_name = failure.request.meta.get("council_name", "unknown")
        self.logger.warning(f"Playwright error for {council_name}: {failure.value}")
        # Could add retry logic with alternative selectors here

    async def _parse_search_results_from_response(self, response, council_name: str, base_url: str):
        """Parse search results directly from an HtmlResponse object."""
        self.logger.info(f"Parsing search results for {council_name}")
        self.logger.info(f"Results URL: {response.url}")
        self.stats["councils_processed"] += 1

        # Look for application links in the results
        app_links = (
            response.css('a.data_text::attr(href)').getall()
            or response.css('a[href*="StdDetails"]::attr(href)').getall()
            or response.xpath('//a[contains(@href, "StdDetails")]/@href').getall()
        )

        self.logger.info(f"Found {len(app_links)} raw links for {council_name}")

        # Filter to only detail page links
        detail_links = [
            link for link in app_links
            if 'StdDetails' in link or 'Details' in link
        ]

        if not detail_links:
            self.logger.warning(f"No application links found for {council_name}")
            self.logger.info(f"Page title: {response.css('title::text').get()}")
            return

        self.logger.info(f"Found {len(detail_links)} applications for {council_name}")

        # Follow each application link
        for link in detail_links:
            app_url = urljoin(response.url, link)

            yield scrapy.Request(
                url=app_url,
                callback=self.parse_application_details,
                cb_kwargs={"council_name": council_name},
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

    async def parse_search_results(self, response, council_name: str, base_url: str):
        """Parse search results page and follow application links."""
        page = response.meta.get("playwright_page")

        self.logger.info(f"Parsing search results for {council_name} (status: {response.status})")
        self.logger.info(f"Response URL: {response.url}")
        self.stats["councils_processed"] += 1

        # Close page first to free resources
        if page:
            await page.close()

        if response.status != 200:
            self.logger.warning(f"Non-200 status for {council_name}: {response.status}")
            return

        # Check if we're on results page or still on search page
        if "GeneralSearch" in response.url:
            self.logger.warning(f"Still on search page for {council_name}, form may not have submitted")
            self.logger.info(f"Page title: {response.css('title::text').get()}")
            return

        # Look for application links in the results
        # ASPX portals use various link patterns
        app_links = (
            response.css('a.data_text::attr(href)').getall()
            or response.css('a[href*="StdDetails"]::attr(href)').getall()
            or response.xpath('//a[contains(@href, "StdDetails")]/@href').getall()
            or response.xpath('//table//a[contains(@href, "ApplicationNumber")]/@href').getall()
            or response.css('table a::attr(href)').getall()
        )

        self.logger.info(f"Found {len(app_links)} raw links for {council_name}")

        # Filter to only detail page links
        detail_links = [
            link for link in app_links
            if 'StdDetails' in link or 'Details' in link or 'ApplicationNumber' in link
        ]

        if not detail_links:
            self.logger.warning(f"No application links found for {council_name}")
            self.logger.info(f"Page content preview: {response.text[:1500]}")
            return

        self.logger.info(f"Found {len(detail_links)} applications for {council_name}")

        # Follow each application link
        for link in detail_links:
            app_url = urljoin(response.url, link)

            yield scrapy.Request(
                url=app_url,
                callback=self.parse_application_details,
                cb_kwargs={"council_name": council_name},
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

        # Check for pagination
        next_page = (
            response.css('a.next::attr(href)').get()
            or response.xpath('//a[contains(text(), "Next")]/@href').get()
            or response.xpath('//a[contains(@class, "next")]/@href').get()
        )

        if next_page:
            self.logger.info(f"Following pagination for {council_name}")
            yield scrapy.Request(
                url=urljoin(response.url, next_page),
                callback=self.parse_search_results,
                cb_kwargs={"council_name": council_name, "base_url": base_url},
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

    async def parse_application_details(self, response, council_name: str):
        """Parse application details page and extract metadata."""
        page = response.meta.get("playwright_page")

        if response.status in [403, 404]:
            self.logger.warning(f"{response.status} for application at {response.url}")
            if page:
                await page.close()
            return

        self.logger.debug(f"Parsing application details for {council_name}: {response.url}")
        self.stats["applications_found"] += 1

        # Close page
        if page:
            await page.close()

        # Create application item
        app_item = PlanningApplicationItem()

        # Extract application reference from URL or page
        app_ref = self._extract_application_reference(response)
        app_item["application_reference"] = app_ref
        app_item["application_url"] = response.url
        app_item["council_name"] = council_name

        # Extract metadata from detail tables
        app_item["site_address"] = self._extract_field(
            response, ["Site Address", "Address", "Location"]
        )
        app_item["proposal"] = self._extract_field(
            response, ["Proposal", "Description", "Development Description"]
        )
        app_item["application_type"] = self._extract_field(
            response, ["Application Type", "Type", "Category"]
        )
        app_item["status"] = self._extract_field(
            response, ["Status", "Application Status", "Current Status"]
        )
        app_item["decision"] = self._extract_field(
            response, ["Decision", "Decision Type"]
        )
        app_item["registration_date"] = self._extract_field(
            response, ["Registration Date", "Date Received", "Received", "Application Registered"]
        )
        app_item["decision_date"] = self._extract_field(
            response, ["Decision Date", "Decision Issued"]
        )
        app_item["applicant_name"] = self._extract_field(
            response, ["Applicant", "Applicant Name"]
        )
        app_item["agent_name"] = self._extract_field(
            response, ["Agent", "Agent Name"]
        )
        app_item["ward"] = self._extract_field(
            response, ["Ward", "Electoral Ward", "Wards"]
        )
        app_item["parish"] = self._extract_field(
            response, ["Parish", "Parishes"]
        )
        app_item["case_officer"] = self._extract_field(
            response, ["Case Officer", "Planning Officer"]
        )

        # Extract postcode from address
        if app_item.get("site_address"):
            app_item["postcode"] = self._extract_postcode(app_item["site_address"])

        # Internal tracking
        app_item["_portal_framework"] = "aspx"
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
            self.logger.debug(f"No documents link found for {app_ref}")
            # Try to extract documents from current page
            for item in self._extract_documents_from_page(response, app_ref, council_name):
                yield item

    def _extract_application_reference(self, response) -> str:
        """Extract application reference from the page."""
        # Merton/ASPX style: <div><span>Application Number</span>26/P0129</div>
        # Get text after the span
        merton_selectors = [
            '//div[span[contains(text(), "Application Number")]]/text()',
            '//li//div[span[contains(text(), "Application Number")]]/text()',
        ]

        for selector in merton_selectors:
            values = response.xpath(selector).getall()
            for value in values:
                cleaned = value.strip()
                if cleaned and cleaned not in ["Application Number", "n/a", "none", "-", ""]:
                    return cleaned

        # Traditional selectors
        ref = (
            response.xpath('//span[contains(@id, "ApplicationNumber")]/text()').get()
            or response.xpath('//td[contains(text(), "Application Number")]/following-sibling::td/text()').get()
            or response.xpath('//th[contains(text(), "Reference")]/following-sibling::td/text()').get()
            or self._extract_field(response, ["Reference", "Ref"])  # Removed "Application Number" since we already tried it
        )

        if ref:
            return ref.strip()

        # Try to extract from URL
        url = response.url
        if "ApplicationNumber=" in url:
            import re
            match = re.search(r'ApplicationNumber=([^&]+)', url)
            if match:
                return match.group(1)

        return "unknown"

    def _extract_field(self, response, labels: list) -> Optional[str]:
        """Extract a field value from a detail page by label.

        Handles multiple HTML structures:
        - Merton style: <div><span>Label</span>Value</div>
        - Table style: <th>Label</th><td>Value</td>
        - Label/value pairs: <td>Label</td><td>Value</td>
        """
        for label in labels:
            # Merton/ASPX style: <div><span>Label</span>Value</div>
            # Get the text content of the div containing the label span
            div_selectors = [
                # Exact match for div containing span with label
                f'//div[span[normalize-space()="{label}"]]/text()',
                # Contains match
                f'//div[span[contains(text(), "{label}")]]/text()',
                # li containing span with label
                f'//li[span[contains(text(), "{label}")]]/text()',
                f'//li//div[span[contains(text(), "{label}")]]/text()',
            ]

            for selector in div_selectors:
                values = response.xpath(selector).getall()
                for value in values:
                    cleaned = value.strip()
                    # Skip if it's just the label itself or empty/na values
                    if cleaned and cleaned.lower() not in ["n/a", "none", "-", ""] and cleaned != label:
                        return cleaned

            # Traditional table selectors
            table_selectors = [
                f'//th[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//td[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//span[contains(text(), "{label}")]/following::span/text()',
                f'//label[contains(text(), "{label}")]/following-sibling::*/text()',
                f'//strong[contains(text(), "{label}")]/following::text()',
                f'//*[contains(@class, "label") and contains(text(), "{label}")]/../*[contains(@class, "value")]/text()',
            ]

            for selector in table_selectors:
                values = response.xpath(selector).getall()
                for value in values:
                    cleaned = value.strip()
                    if cleaned and cleaned.lower() not in ["n/a", "none", "-", ""] and cleaned != label:
                        return cleaned

        return None

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract postcode from address string."""
        if not address:
            return None

        import re
        pattern = r'[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}'
        match = re.search(pattern, address.upper())
        return match.group(0) if match else None

    def _find_documents_link(self, response) -> Optional[str]:
        """Find the link to the documents tab/page."""
        selectors = [
            'a[href*="TabIndex=3"]::attr(href)',
            'a[href*="tabIndex=3"]::attr(href)',
            'a[href*="Documents"]::attr(href)',
        ]

        for selector in selectors:
            links = response.css(selector).getall()
            if links:
                return urljoin(response.url, links[0])

        xpath_selectors = [
            '//a[contains(@href, "TabIndex=3")]/@href',
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
        doc_rows = (
            response.xpath("//table[contains(@class, 'display')]//tbody//tr")
            or response.xpath("//table[@id='documents']//tr[position()>1]")
            or response.xpath("//table[contains(@class, 'documents')]//tr[position()>1]")
            or response.xpath("//div[contains(@class, 'documents')]//table//tr")
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
            or row.xpath(".//a[contains(@href, 'download')]/@href").get()
            or row.xpath(".//a[contains(@href, 'Document')]/@href").get()
            or row.xpath(".//a/@href").get()
        )

        if not doc_url:
            return None

        doc_url = urljoin(response.url, doc_url)

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
        item["_portal_framework"] = "aspx"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("ASPX SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
