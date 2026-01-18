"""
Camden Spider - targeted scraper for Camden's Northgate/ASPX planning portal.

This spider targets specific planning applications by reference number
and downloads ALL documents (bypassing the normal drawing-only filter).

Flow:
1. GET search page to establish session and extract ASP.NET form tokens
2. POST search with application reference number
3. Parse application details page
4. Follow "Related Documents" link/tab
5. Yield ALL documents with project_tag for organization

Target URL: https://planningrecords.camden.gov.uk/NECSWS/PlanningExplorer/GeneralSearch.aspx
"""

from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import scrapy
from scrapy.loader import ItemLoader
from scrapy_playwright.page import PageMethod

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem


class CamdenSpider(scrapy.Spider):
    """
    Spider for Camden's Northgate/ASPX planning portal.

    Targets specific applications by reference and downloads all documents.
    Bypasses normal residential and drawing filters.

    Usage:
        scrapy crawl camden
    """

    name = "camden"

    # Target applications for St Peters Vicarage
    TARGET_APPLICATIONS = [
        "2025/4893/P",
        "2025/5087/A",
    ]

    # Project tag for organization in S3/Supabase
    PROJECT_TAG = "st-peters-vicarage"

    # Base URL for Camden planning portal
    BASE_URL = "https://planningrecords.camden.gov.uk/NECSWS/PlanningExplorer/GeneralSearch.aspx"

    custom_settings = {
        # BYPASS application and document filter pipelines
        # Only use download, compress, S3 upload, and Supabase pipelines
        "ITEM_PIPELINES": {
            "planning_scraper.pipelines.pdf_download.PDFDownloadPipeline": 200,
            "planning_scraper.pipelines.pdf_compress.PDFCompressPipeline": 300,
            "planning_scraper.pipelines.s3_upload.S3UploadPipeline": 400,
            "planning_scraper.pipelines.supabase.SupabasePipeline": 500,
        },
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
        # Conservative rate limiting for council portal
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
        # Handle 403 errors explicitly
        "HTTPERROR_ALLOWED_CODES": [403],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {
            "applications_found": 0,
            "documents_found": 0,
        }
        self._log_startup_config()

    def _log_startup_config(self):
        """Log clear startup configuration."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("CAMDEN SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Project Tag: {self.PROJECT_TAG}")
        self.logger.info(f"  Target Applications: {len(self.TARGET_APPLICATIONS)}")
        for app_ref in self.TARGET_APPLICATIONS:
            self.logger.info(f"    - {app_ref}")
        self.logger.info(f"  Filters: BYPASSED (downloading ALL documents)")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 2.0)}s")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial request to establish session using Playwright."""
        yield scrapy.Request(
            url=self.BASE_URL,
            callback=self.parse_search_page,
            dont_filter=True,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "domcontentloaded"),
                    PageMethod("wait_for_timeout", 2000),  # Small delay for JS to run
                ],
            },
        )

    async def parse_search_page(self, response):
        """
        Parse the search page and use Playwright to submit searches.
        Then follow results to application details.
        """
        page = response.meta.get("playwright_page")

        # Check for 403 Forbidden
        if response.status == 403:
            self.logger.warning(f"Received 403 Forbidden from search page. Trying direct application URLs...")
            if page:
                await page.close()
            for req in self._try_direct_application_access():
                yield req
            return

        self.logger.info(f"Parsing search page (status: {response.status})")

        # Check if we have the search form
        viewstate = response.css('input#__VIEWSTATE::attr(value)').get()
        if not viewstate:
            self.logger.error("Could not find __VIEWSTATE, page structure may have changed")
            if page:
                await page.close()
            for req in self._try_direct_application_access():
                yield req
            return

        self.logger.info(f"Found form tokens (ViewState: {len(viewstate) if viewstate else 0} chars)")

        # Use Playwright to search for each application
        for app_ref in self.TARGET_APPLICATIONS:
            self.logger.info(f"Submitting search for application: {app_ref}")

            # Create a new page for this search to avoid state issues
            yield scrapy.Request(
                url=self.BASE_URL,
                callback=self.parse_with_playwright_search,
                cb_kwargs={"app_ref": app_ref},
                dont_filter=True,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("fill", "#txtApplicationNumber", app_ref),
                        PageMethod("click", "#csbtnSearch"),
                        PageMethod("wait_for_load_state", "networkidle"),
                    ],
                },
            )

        # Close original page
        if page:
            await page.close()

    async def parse_with_playwright_search(self, response, app_ref: str):
        """
        Parse the search results after Playwright has submitted the form.
        """
        page = response.meta.get("playwright_page")

        self.logger.info(f"Parsing Playwright search results for: {app_ref} (status: {response.status})")

        # Close page first
        if page:
            await page.close()

        if response.status != 200:
            self.logger.warning(f"Non-200 status for search: {response.status}")
            return

        # Look for application links in the results
        app_links = (
            response.css('a[href*="StdDetails"]::attr(href)').getall()
            or response.xpath('//a[contains(@href, "StdDetails")]/@href').getall()
            or response.css('table a::attr(href)').getall()
        )

        # Filter to only detail page links
        detail_links = [
            link for link in app_links
            if 'StdDetails' in link or 'Details' in link
        ]

        if not detail_links:
            self.logger.warning(f"No application detail links found for: {app_ref}")
            # Log page content for debugging
            self.logger.debug(f"Page content: {response.text[:3000]}")
            return

        # Follow the first matching link
        app_url = urljoin(response.url, detail_links[0])
        self.logger.info(f"Found application link: {app_url}")

        yield scrapy.Request(
            url=app_url,
            callback=self.parse_application_details,
            cb_kwargs={"app_ref": app_ref},
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_load_state", "networkidle"),
                ],
            },
            dont_filter=True,
        )

    def _try_direct_application_access(self):
        """
        Try to access applications directly via various URL patterns.
        Some councils allow direct links to application details.
        """
        self.logger.info("Attempting direct application access...")

        # Common URL patterns for Northgate/ASPX planning portals
        url_patterns = [
            # Pattern 1: StdDetails with ApplicationNumber parameter
            "https://planningrecords.camden.gov.uk/NECSWS/PlanningExplorer/Generic/StdDetails.aspx?PT=Planning%20Applications%20On-Line&TYPE=PL/PlanningPK.xml&PARAM0={app_ref}",
            # Pattern 2: Direct application number in URL
            "https://planningrecords.camden.gov.uk/NECSWS/PlanningExplorer/Generic/StdDetails.aspx?ApplicationNumber={app_ref}",
            # Pattern 3: With different encoding
            "https://planningrecords.camden.gov.uk/NECSWS/PlanningExplorer/Generic/StdDetails.aspx?PT=Planning%20Applications%20On-Line&PARAM0={app_ref_encoded}",
        ]

        for app_ref in self.TARGET_APPLICATIONS:
            app_ref_encoded = app_ref.replace("/", "%2F")

            for pattern in url_patterns:
                url = pattern.format(app_ref=app_ref, app_ref_encoded=app_ref_encoded)
                self.logger.info(f"Trying direct URL: {url}")

                yield scrapy.Request(
                    url=url,
                    callback=self.parse_application_details,
                    cb_kwargs={"app_ref": app_ref},
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_load_state", "networkidle"),
                        ],
                    },
                    dont_filter=True,
                    errback=self.handle_error,
                )
                # Only try first pattern per app, break if more patterns
                break

    def handle_error(self, failure):
        """Handle request failures."""
        self.logger.error(f"Request failed: {failure.value}")

    def _create_search_request(
        self,
        response,
        app_ref: str,
        viewstate: str,
        viewstate_generator: Optional[str],
        event_validation: Optional[str],
    ):
        """Create a form request to search for a specific application."""
        self.logger.info(f"Submitting search for application: {app_ref}")

        formdata = {
            "__VIEWSTATE": viewstate,
            "txtApplicationNumber": app_ref,
            "csbtnSearch": "Search",
        }

        if viewstate_generator:
            formdata["__VIEWSTATEGENERATOR"] = viewstate_generator
        if event_validation:
            formdata["__EVENTVALIDATION"] = event_validation

        return scrapy.FormRequest(
            url=self.BASE_URL,
            formdata=formdata,
            callback=self.parse_search_results,
            cb_kwargs={"app_ref": app_ref},
            meta={"cookiejar": response.meta.get("cookiejar", 1)},
            dont_filter=True,
        )

    def parse_search_results(self, response, app_ref: str):
        """
        Parse search results page and follow link to application details.
        """
        self.logger.info(f"Parsing search results for: {app_ref}")

        # Look for application links in the results table
        # Northgate portals typically have a table with application links
        app_links = (
            response.css('a[href*="ApplicationNumber"]::attr(href)').getall()
            or response.css('a[href*="StdDetails"]::attr(href)').getall()
            or response.css('table.display_table a::attr(href)').getall()
            or response.xpath('//a[contains(@href, "StdDetails")]/@href').getall()
            or response.xpath('//td/a[contains(text(), "/")]/@href').getall()
        )

        if not app_links:
            # Try to find any link that looks like an application detail page
            all_links = response.css('a::attr(href)').getall()
            app_links = [
                link for link in all_links
                if 'StdDetails' in link or 'Details' in link
            ]

        if not app_links:
            self.logger.warning(f"No application links found for: {app_ref}")
            self.logger.debug(f"Page content: {response.text[:2000]}")
            return

        # Follow the first matching link (should be the application)
        app_url = urljoin(response.url, app_links[0])
        self.logger.info(f"Following application link: {app_url}")

        yield scrapy.Request(
            url=app_url,
            callback=self.parse_application_details,
            cb_kwargs={"app_ref": app_ref},
            meta={"cookiejar": response.meta.get("cookiejar", 1)},
        )

    async def parse_application_details(self, response, app_ref: str):
        """
        Parse application details page and extract metadata.
        Then follow link to documents tab.
        """
        # Close Playwright page if present
        page = response.meta.get("playwright_page")
        if page:
            await page.close()

        # Check for error responses
        if response.status == 403:
            self.logger.warning(f"403 Forbidden accessing application details for: {app_ref}")
            return
        if response.status == 404:
            self.logger.warning(f"404 Not Found for application: {app_ref}")
            return

        self.logger.info(f"Parsing application details for: {app_ref} (status: {response.status})")
        self.stats["applications_found"] += 1

        # Create application item
        app_item = PlanningApplicationItem()

        # Core identification
        app_item["application_reference"] = app_ref
        app_item["application_url"] = response.url
        app_item["council_name"] = "camden"
        app_item["project_tag"] = self.PROJECT_TAG

        # Extract metadata from detail tables
        # Northgate uses various table structures
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
            response, ["Registration Date", "Date Received", "Received"]
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
            response, ["Ward", "Electoral Ward"]
        )
        app_item["postcode"] = self._extract_postcode(app_item.get("site_address", ""))

        # Internal tracking
        app_item["_portal_framework"] = "aspx"
        app_item["_scraped_at"] = datetime.utcnow().isoformat()

        yield app_item

        # Find and follow the documents tab/link
        docs_url = self._find_documents_link(response)

        if docs_url:
            self.logger.info(f"Following documents link: {docs_url}")
            yield scrapy.Request(
                url=docs_url,
                callback=self.parse_documents_tab,
                cb_kwargs={"app_ref": app_ref},
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                    ],
                },
            )
        else:
            self.logger.warning(f"No documents link found for: {app_ref}")
            # Try to extract documents from current page
            for item in self._extract_documents_from_page(response, app_ref):
                yield item

    def _extract_field(self, response, labels: list) -> Optional[str]:
        """
        Extract a field value from a detail table by label.
        Tries multiple label variations.
        """
        for label in labels:
            # Try various table structures
            selectors = [
                f'//th[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//td[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//span[contains(text(), "{label}")]/following::span/text()',
                f'//label[contains(text(), "{label}")]/following-sibling::*/text()',
                f'//strong[contains(text(), "{label}")]/following::text()',
                f'//*[contains(@class, "label") and contains(text(), "{label}")]/../*[contains(@class, "value")]/text()',
            ]

            for selector in selectors:
                values = response.xpath(selector).getall()
                for value in values:
                    cleaned = value.strip()
                    if cleaned and cleaned.lower() not in ["n/a", "none", "-"]:
                        return cleaned

        return None

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract postcode from address string."""
        if not address:
            return None

        import re
        # UK postcode pattern
        pattern = r'[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}'
        match = re.search(pattern, address.upper())
        return match.group(0) if match else None

    def _find_documents_link(self, response) -> Optional[str]:
        """Find the link to the documents tab/page."""
        # Try various selectors for document links
        doc_link_selectors = [
            'a[href*="TabIndex=3"]::attr(href)',
            'a[href*="tabIndex=3"]::attr(href)',
            'a[href*="Documents"]::attr(href)',
            'a:contains("Documents")::attr(href)',
            'a:contains("Related Documents")::attr(href)',
            'a:contains("View Documents")::attr(href)',
        ]

        for selector in doc_link_selectors:
            links = response.css(selector).getall()
            if links:
                return urljoin(response.url, links[0])

        # Try XPath
        xpath_selectors = [
            '//a[contains(@href, "TabIndex=3")]/@href',
            '//a[contains(text(), "Documents")]/@href',
            '//a[contains(text(), "Related Documents")]/@href',
            '//a[contains(text(), "View")]/@href',
            '//li[contains(@class, "tab")]//a[contains(text(), "Document")]/@href',
        ]

        for selector in xpath_selectors:
            links = response.xpath(selector).getall()
            if links:
                return urljoin(response.url, links[0])

        return None

    async def parse_documents_tab(self, response, app_ref: str):
        """
        Parse the documents tab and extract ALL document links.
        """
        # Close Playwright page if present
        page = response.meta.get("playwright_page")
        if page:
            await page.close()

        self.logger.info(f"Parsing documents tab for: {app_ref}")
        for item in self._extract_documents_from_page(response, app_ref):
            yield item

    def _extract_documents_from_page(self, response, app_ref: str):
        """Extract all documents from a page."""
        # Look for document links in various formats
        doc_rows = (
            response.xpath("//table[contains(@class, 'display')]//tbody//tr")
            or response.xpath("//table[@id='documents']//tr[position()>1]")
            or response.xpath("//table[contains(@class, 'documents')]//tr[position()>1]")
            or response.xpath("//div[contains(@class, 'documents')]//table//tr")
            or response.xpath("//table//tr[td[contains(@class, 'document')]]")
        )

        if doc_rows:
            self.logger.info(f"Found {len(doc_rows)} document rows")
            for row in doc_rows:
                yield from self._extract_document_from_row(row, response, app_ref)
        else:
            # Fallback: find all PDF/document links on the page
            self.logger.info("No document table found, searching for PDF links...")
            yield from self._extract_pdf_links(response, app_ref)

    def _extract_document_from_row(self, row, response, app_ref: str):
        """Extract document info from a table row."""
        # Look for document link
        doc_url = (
            row.xpath(".//a[contains(@href, '.pdf')]/@href").get()
            or row.xpath(".//a[contains(@href, 'ViewDocument')]/@href").get()
            or row.xpath(".//a[contains(@href, 'download')]/@href").get()
            or row.xpath(".//a[contains(@href, 'Document')]/@href").get()
            or row.xpath(".//a/@href").get()
        )

        if not doc_url:
            return

        doc_url = urljoin(response.url, doc_url)

        # Extract filename/description
        filename = (
            row.xpath(".//a/text()").get()
            or row.xpath(".//td[1]/text()").get()
            or row.xpath(".//td[contains(@class, 'description')]/text()").get()
            or self._extract_filename_from_url(doc_url)
        )

        if filename:
            filename = filename.strip()

        # Extract document type/description from other columns
        doc_description = (
            row.xpath(".//td[2]/text()").get()
            or row.xpath(".//td[contains(@class, 'type')]/text()").get()
            or ""
        )

        yield self._create_document_item(
            doc_url, filename, doc_description, response.url, app_ref
        )

    def _extract_pdf_links(self, response, app_ref: str):
        """Extract all PDF links from the page."""
        # Find all links that look like documents
        pdf_links = (
            response.xpath("//a[contains(@href, '.pdf')]/@href").getall()
            or response.xpath("//a[contains(@href, 'ViewDocument')]/@href").getall()
        )

        self.logger.info(f"Found {len(pdf_links)} PDF links")

        for doc_url in pdf_links:
            doc_url = urljoin(response.url, doc_url)
            filename = self._extract_filename_from_url(doc_url)

            yield self._create_document_item(
                doc_url, filename, "", response.url, app_ref
            )

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import unquote
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Get last path component
        filename = path.split("/")[-1]

        # Remove query string if present
        if "?" in filename:
            filename = filename.split("?")[0]

        return filename if filename else "document.pdf"

    def _create_document_item(
        self,
        doc_url: str,
        filename: str,
        description: str,
        source_url: str,
        app_ref: str,
    ):
        """Create a DocumentItem with all required fields."""
        self.stats["documents_found"] += 1

        item = DocumentItem()

        # Source information
        item["document_url"] = doc_url
        item["source_url"] = source_url
        item["filename"] = filename or "document.pdf"

        # Parent application reference
        item["application_reference"] = app_ref
        item["council_name"] = "camden"

        # Project tag for organization
        item["project_tag"] = self.PROJECT_TAG

        # Set matches_pattern=True to bypass document filter
        # (filter checks this flag in process_item)
        item["matches_pattern"] = True
        item["document_type"] = "document"  # Generic type since not filtering

        # Internal tracking
        item["_portal_framework"] = "aspx"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        self.logger.debug(f"Created document item: {filename}")

        return item

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("CAMDEN SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info(f"  Project Tag: {self.PROJECT_TAG}")
        self.logger.info("=" * 60)
        self.logger.info("")
