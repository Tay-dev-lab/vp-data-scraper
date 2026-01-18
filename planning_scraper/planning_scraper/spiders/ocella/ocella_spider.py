"""
OCELLA Spider - scrapes UK planning portals using the OCELLA framework.

OCELLA is used by several councils including Havering and Hillingdon.
Simple HTTP FormRequest-based spider (NO Playwright needed).

Flow:
1. GET search page to establish session
2. POST search with date range (DD-MM-YY format)
3. Parse search results for application links
4. Follow each application to details page
5. Extract metadata and documents
6. Yield application and document items
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin

import scrapy

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_ocella_urls


class OcellaSpider(scrapy.Spider):
    """
    Spider for OCELLA-based planning portals.

    Handles date-based searches using form submissions.
    Uses browser impersonation for compatibility.

    Usage:
        scrapy crawl ocella -a region=london -a days_back=30
        scrapy crawl ocella -a council=havering -a days_back=30
        scrapy crawl ocella -a council=hillingdon -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "ocella"

    custom_settings = {
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 2.0,
        "COOKIES_ENABLED": True,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.5,
        "DOWNLOAD_TIMEOUT": 60,
    }

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
        self.portal_urls = get_ocella_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No OCELLA portals found for region='{region}', council='{council}'. "
                "Valid councils: havering, hillingdon"
            )

        # Calculate date range
        # OCELLA uses DD-MM-YY format (e.g., '01-01-25' for Jan 1, 2025)
        if start_date and end_date:
            # Convert from DD/MM/YYYY to DD-MM-YY
            self.start_date = self._convert_date_format(start_date)
            self.end_date = self._convert_date_format(end_date)
            self.start_date_display = start_date
            self.end_date_display = end_date
        else:
            end = datetime.now()
            start = end - timedelta(days=int(days_back))
            self.start_date = start.strftime("%d-%m-%y")
            self.end_date = end.strftime("%d-%m-%y")
            self.start_date_display = start.strftime("%d/%m/%Y")
            self.end_date_display = end.strftime("%d/%m/%Y")

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

    def _convert_date_format(self, date_str: str) -> str:
        """Convert date from DD/MM/YYYY to DD-MM-YY format."""
        try:
            # Parse DD/MM/YYYY
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            # Return DD-MM-YY
            return dt.strftime("%d-%m-%y")
        except ValueError:
            # Already in correct format or invalid
            return date_str

    def _log_startup_config(self):
        """Log clear startup configuration."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("OCELLA SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date_display} to {self.end_date_display}")
        self.logger.info(f"  OCELLA Date Format: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 2.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests for each OCELLA portal."""
        for council_name, url in self.portal_urls.items():
            self.logger.info(f"Starting scrape for council: {council_name}")

            yield scrapy.Request(
                url=url,
                callback=self.parse_search_page,
                cb_kwargs={"council_name": council_name, "base_url": url},
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "impersonate": "chrome120",
                },
            )

    def parse_search_page(self, response, council_name: str, base_url: str):
        """Parse search page and submit date-based search form."""
        self.logger.debug(f"Parsing search page for {council_name}: {response.url}")

        # Build form data for OCELLA search
        formdata = {
            "reference": "",
            "location": "",
            "OcellaPlanningSearch.postcode": "",
            "area": "",
            "applicant": "",
            "agent": "",
            "receivedFrom": "",
            "receivedTo": "",
            "decidedFrom": self.start_date,
            "decidedTo": self.end_date,
            "action": "Search",
        }

        # Build search URL
        search_url = response.url.rsplit("/", 1)[0] + "/planningSearch"

        # Build headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": response.url.rsplit("/", 2)[0],
            "Referer": response.url,
            "Connection": "keep-alive",
        }

        self.logger.info(
            f"Submitting search for {council_name}: {self.start_date} to {self.end_date}"
        )

        yield scrapy.FormRequest(
            url=search_url,
            formdata=formdata,
            headers=headers,
            callback=self.parse_search_results,
            cb_kwargs={"council_name": council_name, "base_url": base_url},
            dont_filter=True,
            errback=self.handle_error,
            meta={
                "council_name": council_name,
                "impersonate": "chrome120",
            },
        )

    def handle_error(self, failure):
        """Handle request errors."""
        self.logger.error(f"Request failed: {failure.value}")
        self.logger.error(f"Request URL: {failure.request.url}")

    def parse_search_results(self, response, council_name: str, base_url: str):
        """Parse search results page and follow application links."""
        self.logger.info(f"Parsing search results for {council_name} (status: {response.status})")
        self.stats["councils_processed"] += 1

        # Extract application links from results table
        # OCELLA uses: //tr/td[1]/a[starts-with(@href, "planningDetails")]
        links = response.xpath(
            '//tr/td[1]/a[starts-with(@href, "planningDetails")]/@href'
        ).getall()

        if not links:
            # Try alternative selectors
            links = (
                response.xpath('//a[contains(@href, "planningDetails")]/@href').getall()
                or response.xpath('//table//a[contains(@href, "Details")]/@href').getall()
            )

        if links:
            self.logger.info(f"Found {len(links)} applications for {council_name}")
        else:
            self.logger.warning(f"No applications found for {council_name}")
            self.logger.debug(f"Page title: {response.css('title::text').get()}")
            return

        for link in links:
            absolute_url = response.urljoin(link)
            self.stats["applications_found"] += 1

            yield scrapy.Request(
                url=absolute_url,
                callback=self.parse_application_details,
                cb_kwargs={
                    "council_name": council_name,
                    "application_url": absolute_url,
                },
                meta={
                    "council_name": council_name,
                    "impersonate": "chrome120",
                },
            )

        # Check for pagination
        next_page = (
            response.xpath('//a[contains(text(), "Next")]/@href').get()
            or response.xpath('//a[contains(@class, "next")]/@href').get()
        )

        if next_page:
            self.logger.debug(f"Following pagination for {council_name}")
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_search_results,
                cb_kwargs={"council_name": council_name, "base_url": base_url},
                meta={
                    "council_name": council_name,
                    "impersonate": "chrome120",
                },
            )

    def parse_application_details(
        self, response, council_name: str, application_url: str
    ):
        """Parse application details page."""
        self.logger.debug(f"Parsing application details: {application_url}")

        # Build application data from table rows
        app_data = {
            "council_name": council_name,
            "application_url": application_url,
        }

        # Field mappings for OCELLA detail tables
        # Format: //tr[td/strong[contains(text(), "Label")]]/td[2]/text()
        field_mapping = {
            "Reference": "application_reference",
            "Status": "status",
            "Proposal": "proposal",
            "Location": "site_address",
            "Parish": "parish",
            "Ward": "ward",
            "Case Officer": "case_officer",
            "Received": "registration_date",
            "Validated": "valid_from",
            "Decision By": "target_decision_date",
            "Decided": "decision_date",
            "Decision": "decision",
            "Applicant": "applicant_name",
            "Agent": "agent_name",
            "Application Type": "application_type",
            "Development Type": "development_type",
        }

        # Extract fields from detail table
        for label, field_name in field_mapping.items():
            value = response.xpath(
                f'//tr[td/strong[contains(text(), "{label}")]]/td[2]/text()'
            ).get()

            if value:
                value = value.strip()
                if value and value.lower() not in ["n/a", "none", "-", ""]:
                    app_data[field_name] = value

        # Also try extracting from links (e.g., Case Officer might be a link)
        for label in ["Case Officer"]:
            if label == "Case Officer" and "case_officer" not in app_data:
                value = response.xpath(
                    f'//tr[td/strong[contains(text(), "{label}")]]/td[2]/a/text()'
                ).get()
                if value:
                    app_data["case_officer"] = value.strip()

        # Extract postcode from address if available
        if app_data.get("site_address"):
            app_data["postcode"] = self._extract_postcode(app_data["site_address"])

        # Yield the application item
        yield self._create_application_item(app_data)

        # Extract documents from the page
        # OCELLA typically shows documents on the same page or via a tab
        yield from self._extract_documents(response, app_data)

    def _extract_documents(self, response, app_data: Dict[str, Any]):
        """Extract documents from application details page."""
        app_ref = app_data.get("application_reference", "unknown")

        # Try to find document links
        # Look for PDF links
        pdf_links = response.xpath("//a[contains(@href, '.pdf')]/@href").getall()

        # Look for document viewer links
        doc_links = response.xpath(
            "//a[contains(@href, 'viewDocument') or contains(@href, 'ViewDocument')]/@href"
        ).getall()

        # Look for document table rows
        doc_rows = (
            response.xpath("//table[contains(@class, 'documents')]//tr[position()>1]")
            or response.xpath("//div[contains(@class, 'documents')]//a")
            or response.xpath("//div[@id='documents']//a")
        )

        all_doc_urls = set(pdf_links + doc_links)

        # Extract from document rows if found
        for row in doc_rows:
            doc_url = (
                row.xpath(".//a[contains(@href, '.pdf')]/@href").get()
                or row.xpath(".//a/@href").get()
            )
            if doc_url:
                all_doc_urls.add(doc_url)

        if not all_doc_urls:
            self.logger.debug(f"No documents found for {app_ref}")
            return

        self.logger.debug(f"Found {len(all_doc_urls)} documents for {app_ref}")

        for doc_url in all_doc_urls:
            doc_url = response.urljoin(doc_url)

            # Get filename from link text or URL
            link_elem = response.xpath(f"//a[@href='{doc_url}' or contains(@href, '{doc_url}')]")
            filename = ""
            if link_elem:
                filename = link_elem.xpath("string(.)").get("").strip()

            if not filename:
                filename = self._extract_filename_from_url(doc_url)

            # Skip non-PDF files
            if not self._is_likely_pdf(doc_url, filename):
                continue

            self.stats["documents_found"] += 1

            yield DocumentItem(
                application_reference=app_data.get("application_reference"),
                council_name=app_data.get("council_name"),
                document_url=doc_url,
                filename=filename,
                source_url=response.url,
                _portal_framework="ocella",
                _scraped_at=datetime.utcnow().isoformat(),
            )

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract postcode from address string."""
        if not address:
            return None

        import re

        pattern = r"[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}"
        match = re.search(pattern, address.upper())
        return match.group(0) if match else None

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import unquote

        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = path.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]
        return filename if filename else "document.pdf"

    def _is_likely_pdf(self, url: str, filename: str) -> bool:
        """Check if a document is likely a PDF."""
        url_lower = url.lower()
        filename_lower = filename.lower()

        # Positive signals
        if ".pdf" in url_lower or ".pdf" in filename_lower:
            return True

        if "viewdocument" in url_lower or "download" in url_lower:
            return True

        # Negative signals - skip images, HTML, etc.
        skip_extensions = [".jpg", ".jpeg", ".png", ".gif", ".html", ".htm"]
        for ext in skip_extensions:
            if ext in url_lower or ext in filename_lower:
                return False

        # Default to true for unknown types
        return True

    def _create_application_item(
        self, app_data: Dict[str, Any]
    ) -> PlanningApplicationItem:
        """Create a PlanningApplicationItem from parsed data."""
        item = PlanningApplicationItem()

        for key, value in app_data.items():
            if value and key in item.fields:
                item[key] = value

        item["_portal_framework"] = "ocella"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("OCELLA SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
