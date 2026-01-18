"""
Agile Applications Spider - scrapes UK planning portals using the Agile Applications API.

Agile Applications provides a REST API for planning data, making this one of
the simplest spiders - NO web scraping needed, just direct API calls.

Flow:
1. Make API request with date range
2. Parse JSON response containing application data
3. For each application, fetch documents from application detail page
4. Yield application and document items
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin, urlencode

import scrapy

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_agile_urls


class AgileSpider(scrapy.Spider):
    """
    Spider for Agile Applications-based planning portals.

    Uses the Agile REST API for direct JSON data access.
    No web scraping required - much faster and more reliable.

    Usage:
        scrapy crawl agile -a region=london -a days_back=30
        scrapy crawl agile -a council=redbridge -a days_back=30
        scrapy crawl agile -a council=redbridge -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "agile"

    # API endpoint
    API_URL = "https://planningapi.agileapplications.co.uk/api/application/search"

    custom_settings = {
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_DELAY": 1.0,
        "COOKIES_ENABLED": True,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2.0,
        "DOWNLOAD_TIMEOUT": 60,
        # Enable scrapy-impersonate for browser TLS fingerprinting
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_impersonate.ImpersonateDownloadHandler",
            "https": "scrapy_impersonate.ImpersonateDownloadHandler",
        },
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        # Let curl_cffi set appropriate User-Agent based on impersonated browser
        "USER_AGENT": None,
        # Disable proxy middleware - API needs direct access
        "DOWNLOADER_MIDDLEWARES": {
            "planning_scraper.middlewares.proxy.ProxyMiddleware": None,
        },
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
        self.portal_urls = get_agile_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No Agile portals found for region='{region}', council='{council}'. "
                "Valid councils: redbridge, islington"
            )

        # Calculate date range
        # Agile API uses YYYY-MM-DD format
        if start_date and end_date:
            self.start_date = self._convert_date_format(start_date)
            self.end_date = self._convert_date_format(end_date)
            self.start_date_display = start_date
            self.end_date_display = end_date
        else:
            end = datetime.now()
            start = end - timedelta(days=int(days_back))
            self.start_date = start.strftime("%Y-%m-%d")
            self.end_date = end.strftime("%Y-%m-%d")
            self.start_date_display = start.strftime("%d/%m/%Y")
            self.end_date_display = end.strftime("%d/%m/%Y")

        # Build allowed domains
        self.allowed_domains = ["planningapi.agileapplications.co.uk"]
        for config in self.portal_urls.values():
            domain = urlparse(config["url"]).netloc
            if domain not in self.allowed_domains:
                self.allowed_domains.append(domain)

        # Stats
        self.stats = {
            "councils_processed": 0,
            "applications_found": 0,
            "documents_found": 0,
        }

        # Log startup configuration
        self._log_startup_config()

    def _convert_date_format(self, date_str: str) -> str:
        """Convert date from DD/MM/YYYY to YYYY-MM-DD format."""
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return date_str

    def _log_startup_config(self):
        """Log clear startup configuration."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("AGILE SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date_display} to {self.end_date_display}")
        self.logger.info(f"  API Date Format: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 1.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")

    def _get_api_headers(self, x_client: str, portal_url: str) -> Dict[str, str]:
        """Generate API headers for a specific council.

        Args:
            x_client: The x-client header value (may differ from council name)
            portal_url: The portal URL for Origin/Referer headers
        """
        # Extract origin from portal URL
        parsed = urlparse(portal_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en",
            "x-client": x_client,
            "x-product": "CITIZENPORTAL",
            "x-service": "PA",
            "Origin": origin,
            "Connection": "keep-alive",
            "Referer": f"{origin}/",
        }

    def start_requests(self):
        """Generate API requests for each Agile portal."""
        for council_name, config in self.portal_urls.items():
            portal_url = config["url"]
            x_client = config["x_client"]

            self.logger.info(f"Starting API request for council: {council_name} (x-client: {x_client})")

            # Build API URL with query parameters
            params = {
                "decisionDateFrom": self.start_date,
                "decisionDateTo": self.end_date,
            }
            api_url = f"{self.API_URL}?{urlencode(params)}"

            # Get headers for this council
            headers = self._get_api_headers(x_client, portal_url)

            yield scrapy.Request(
                url=api_url,
                headers=headers,
                callback=self.parse_api_response,
                cb_kwargs={
                    "council_name": council_name,
                    "portal_url": portal_url,
                },
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "impersonate": "chrome120",
                },
            )

    def parse_api_response(self, response, council_name: str, portal_url: str):
        """Parse the API JSON response."""
        self.logger.info(f"Parsing API response for {council_name} (status: {response.status})")
        self.stats["councils_processed"] += 1

        if response.status != 200:
            self.logger.error(f"API request failed for {council_name}: status {response.status}")
            self.logger.error(f"Response: {response.text[:500]}")
            return

        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"Failed to parse JSON for {council_name}: {e}")
            self.logger.error(f"Response: {response.text[:500]}")
            return

        # Check for API errors
        if isinstance(data, list) and len(data) > 0 and "code" in data[0]:
            self.logger.error(f"API error for {council_name}: {data}")
            return

        results = data.get("results", [])
        total = data.get("total", len(results))

        self.logger.info(f"Found {total} applications for {council_name}")

        for result in results:
            self.stats["applications_found"] += 1

            # Create application item from API data
            app_item = self._create_application_item(result, council_name, portal_url)
            yield app_item

            # Follow to application detail page to get documents
            app_id = result.get("id")
            if app_id:
                detail_url = f"{portal_url.rstrip('/')}/application-details/{app_id}"
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_documents_page,
                    cb_kwargs={
                        "council_name": council_name,
                        "application_reference": result.get("reference"),
                        "app_id": app_id,
                    },
                    meta={
                        "council_name": council_name,
                        "impersonate": "chrome120",
                    },
                    dont_filter=True,
                )

    def _create_application_item(
        self, result: Dict[str, Any], council_name: str, portal_url: str
    ) -> PlanningApplicationItem:
        """Create a PlanningApplicationItem from API response data."""
        item = PlanningApplicationItem()

        # Core identification
        app_id = result.get("id")
        item["application_reference"] = result.get("reference")
        item["application_url"] = f"{portal_url.rstrip('/')}/application-details/{app_id}"
        item["council_name"] = council_name

        # Location
        item["site_address"] = result.get("location")
        item["postcode"] = result.get("postcode")
        item["ward"] = result.get("ward")
        item["parish"] = result.get("parish")

        # Application details
        item["application_type"] = result.get("applicationType")
        item["proposal"] = result.get("proposal")
        item["status"] = result.get("status")
        item["decision"] = result.get("decisionText")

        # Dates (API returns ISO format)
        item["registration_date"] = self._format_date(result.get("registrationDate"))
        item["valid_from"] = self._format_date(result.get("validDate"))
        item["decision_date"] = self._format_date(result.get("decisionDate"))

        # People
        applicant_name = result.get("applicantName") or result.get("applicantSurname")
        if applicant_name:
            item["applicant_name"] = applicant_name

        agent_name = result.get("agentName")
        if agent_name:
            item["agent_name"] = agent_name

        officer_name = result.get("officerName")
        if officer_name:
            item["case_officer"] = officer_name

        # Internal tracking
        item["_portal_framework"] = "agile"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def _format_date(self, date_str: Optional[str]) -> Optional[str]:
        """Format ISO date to DD/MM/YYYY for consistency."""
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return date_str

    def parse_documents_page(
        self, response, council_name: str, application_reference: str, app_id: int
    ):
        """Parse application detail page for documents."""
        self.logger.debug(f"Parsing documents for {application_reference}")

        # Agile uses JavaScript to load documents, so we look for document links
        # or may need to call a documents API endpoint

        # Try to find document links in the page
        doc_links = (
            response.xpath("//a[contains(@href, '.pdf')]/@href").getall()
            or response.xpath("//a[contains(@href, 'document')]/@href").getall()
            or response.xpath("//a[contains(@href, 'download')]/@href").getall()
        )

        # Also try to find document table/list
        doc_rows = response.xpath(
            "//table[contains(@class, 'document')]//tr[position()>1]"
        )

        if doc_rows:
            for row in doc_rows:
                doc_url = row.xpath(".//a/@href").get()
                doc_name = row.xpath(".//a/text()").get() or row.xpath(".//td[1]/text()").get()

                if doc_url:
                    doc_url = response.urljoin(doc_url)
                    self.stats["documents_found"] += 1

                    yield DocumentItem(
                        application_reference=application_reference,
                        council_name=council_name,
                        document_url=doc_url,
                        filename=doc_name.strip() if doc_name else self._extract_filename_from_url(doc_url),
                        source_url=response.url,
                        _portal_framework="agile",
                        _scraped_at=datetime.utcnow().isoformat(),
                    )
        elif doc_links:
            for doc_url in doc_links:
                doc_url = response.urljoin(doc_url)
                self.stats["documents_found"] += 1

                yield DocumentItem(
                    application_reference=application_reference,
                    council_name=council_name,
                    document_url=doc_url,
                    filename=self._extract_filename_from_url(doc_url),
                    source_url=response.url,
                    _portal_framework="agile",
                    _scraped_at=datetime.utcnow().isoformat(),
                )
        else:
            # Agile loads documents via JavaScript/API - may need API call
            self.logger.debug(f"No documents found in HTML for {application_reference}")

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import unquote

        parsed = urlparse(url)
        path = unquote(parsed.path)
        filename = path.split("/")[-1]
        if "?" in filename:
            filename = filename.split("?")[0]
        return filename if filename else "document.pdf"

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("AGILE SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
