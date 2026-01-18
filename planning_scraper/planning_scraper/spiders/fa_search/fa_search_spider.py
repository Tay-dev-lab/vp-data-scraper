"""
FA_SEARCH (Tascomi) Spider - scrapes UK planning portals using the FA_SEARCH/Tascomi framework.

This spider handles portals with WAF token protection, requiring browser automation
for initial token extraction before making form-based requests.

Supports: Barking & Dagenham, Hackney, Harrow, Waltham Forest (London boroughs)

Flow:
1. Use Playwright to load portal and extract WAF token from cookies
2. POST search with date range using extracted token
3. Parse AJAX response for application IDs
4. Fetch application details via getApplication endpoint
5. Yield application and document items
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin

import scrapy
from scrapy import FormRequest
from scrapy_playwright.page import PageMethod

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_fa_search_urls


def _get_playwright_proxy_config():
    """Get proxy config for Playwright from environment."""
    proxy_url = os.environ.get("PROXY_URL")
    if not proxy_url:
        return None

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


class FaSearchSpider(scrapy.Spider):
    """
    Spider for FA_SEARCH (Tascomi) based planning portals.

    Handles WAF token extraction and form-based searches.

    Usage:
        scrapy crawl fa_search -a region=london -a days_back=30
        scrapy crawl fa_search -a council=hackney -a days_back=30
        scrapy crawl fa_search -a council=harrow -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "fa_search"

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
            # Handle WAF error codes
            "HTTPERROR_ALLOWED_CODES": [403, 406],
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
        self.portal_urls = get_fa_search_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No FA_SEARCH portals found for region='{region}', council='{council}'. "
                "Valid councils: barking, hackney, harrow, waltham_forest"
            )

        # Calculate date range (FA_SEARCH uses DD-MM-YYYY format)
        if start_date and end_date:
            self.start_date = self._convert_date_format(start_date)
            self.end_date = self._convert_date_format(end_date)
            self.start_date_display = start_date
            self.end_date_display = end_date
        else:
            end = datetime.now()
            start = end - timedelta(days=int(days_back))
            self.start_date = start.strftime("%d-%m-%Y")
            self.end_date = end.strftime("%d-%m-%Y")
            self.start_date_display = start.strftime("%d/%m/%Y")
            self.end_date_display = end.strftime("%d/%m/%Y")

        # Build allowed domains from URLs
        self.allowed_domains = list(
            {urlparse(config["url"]).netloc.split(":")[0] for config in self.portal_urls.values()}
        )

        # Store WAF tokens per domain
        self.waf_tokens: Dict[str, str] = {}

        # Stats
        self.stats = {
            "councils_processed": 0,
            "applications_found": 0,
            "documents_found": 0,
        }

        # Log startup configuration
        self._log_startup_config()

    def _convert_date_format(self, date_str: str) -> str:
        """Convert date from DD/MM/YYYY to DD-MM-YYYY format."""
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%d-%m-%Y")
        except ValueError:
            return date_str.replace("/", "-")

    def _log_startup_config(self):
        """Log clear startup configuration."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("FA_SEARCH SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date_display} to {self.end_date_display}")
        self.logger.info(f"  FA_SEARCH Date Format: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 3.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests to extract WAF tokens."""
        for council_name, config in self.portal_urls.items():
            portal_url = config["url"]
            self.logger.info(f"Starting WAF token extraction for council: {council_name}")

            yield scrapy.Request(
                url=portal_url,
                callback=self.extract_waf_token,
                cb_kwargs={"council_name": council_name, "config": config},
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("wait_for_timeout", 3000),
                    ],
                },
            )

    async def extract_waf_token(self, response, council_name: str, config: Dict[str, str]):
        """Extract WAF token from cookies using Playwright."""
        page = response.meta.get("playwright_page")
        domain = urlparse(config["url"]).netloc

        if not page:
            self.logger.error(f"No Playwright page for {council_name}")
            return

        try:
            # Get all cookies from the page
            cookies = await page.context.cookies()
            self.logger.debug(f"Found {len(cookies)} cookies for {council_name}")

            # Look for WAF token (aws-waf-token or similar)
            waf_token = None
            for cookie in cookies:
                cookie_name = cookie.get("name", "").lower()
                if "waf" in cookie_name or cookie_name in ["aws-waf-token", "__cf_bm"]:
                    waf_token = cookie.get("value")
                    self.logger.info(f"Found WAF token for {council_name}: {cookie.get('name')}")
                    break

            if waf_token:
                self.waf_tokens[domain] = waf_token

            # Close the page
            await page.close()

            # Now submit the search form - yield each request
            for request in self._submit_search(council_name, config, waf_token):
                yield request

        except Exception as e:
            self.logger.error(f"Error extracting WAF token for {council_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if page:
                await page.close()

    def _submit_search(self, council_name: str, config: Dict[str, str], waf_token: Optional[str]):
        """Submit search form request."""
        search_url = config.get("search_url", config["url"])
        domain = urlparse(config["url"]).netloc

        self.logger.info(f"Submitting search for {council_name}: {self.start_date} to {self.end_date}")

        # Build form data
        formdata = {
            "fa": "search",
            "submitted": "true",
            "decision_issued_date_from": self.start_date,
            "decision_issued_date_to": self.end_date,
        }

        # Build headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-GB,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": f"https://{domain}",
            "Referer": config["url"],
        }

        # Build cookies
        cookies = {"userlanguage": "en"}
        if waf_token:
            cookies["aws-waf-token"] = waf_token

        yield FormRequest(
            url=search_url,
            formdata=formdata,
            headers=headers,
            cookies=cookies,
            callback=self.parse_search_results,
            cb_kwargs={
                "council_name": council_name,
                "config": config,
                "page": 1,
            },
            dont_filter=True,
            meta={
                "council_name": council_name,
                "waf_token": waf_token,
            },
        )

    def parse_search_results(self, response, council_name: str, config: Dict[str, str], page: int):
        """Parse search results and extract application IDs."""
        self.logger.info(f"Parsing search results for {council_name} (page {page}, status: {response.status})")
        self.stats["councils_processed"] += 1

        if response.status in [403, 406]:
            self.logger.warning(f"WAF blocked request for {council_name}: status {response.status}")
            return

        # Extract application IDs from buttons
        application_ids = response.css('button.view_application::attr(data-id)').getall()

        # Alternative selectors if the first doesn't work
        if not application_ids:
            application_ids = (
                response.css('[data-id]::attr(data-id)').getall()
                or response.xpath('//button[contains(@class, "view")]/@data-id').getall()
                or response.xpath('//*[@onclick and contains(@onclick, "getApplication")]/@data-id').getall()
            )

        self.logger.info(f"Found {len(application_ids)} applications for {council_name} (page {page})")

        # Fetch details for each application
        for app_id in application_ids:
            yield from self._fetch_application_details(app_id, council_name, config, response)

        # Check for more results - request next page
        if application_ids:
            next_page = page + 1
            search_url = config.get("search_url", config["url"])
            domain = urlparse(config["url"]).netloc
            waf_token = response.meta.get("waf_token")

            formdata = {
                "fa": "search",
                "page": str(next_page),
                "ajax": "true",
                "result_loader": "true",
                "submitted": "true",
                "decision_issued_date_from": self.start_date,
                "decision_issued_date_to": self.end_date,
            }

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-GB,en;q=0.5",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": f"https://{domain}",
                "Referer": config["url"],
            }

            cookies = {"userlanguage": "en"}
            if waf_token:
                cookies["aws-waf-token"] = waf_token

            yield FormRequest(
                url=search_url,
                formdata=formdata,
                headers=headers,
                cookies=cookies,
                callback=self.parse_search_results,
                cb_kwargs={
                    "council_name": council_name,
                    "config": config,
                    "page": next_page,
                },
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "waf_token": waf_token,
                },
            )

    def _fetch_application_details(self, app_id: str, council_name: str, config: Dict[str, str], response):
        """Fetch application details via getApplication endpoint."""
        search_url = config.get("search_url", config["url"])
        waf_token = response.meta.get("waf_token")

        formdata = {
            "fa": "getApplication",
            "id": app_id,
        }

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": response.url,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        cookies = {"userlanguage": "en"}
        if waf_token:
            cookies["aws-waf-token"] = waf_token

        yield FormRequest(
            url=search_url,
            formdata=formdata,
            headers=headers,
            cookies=cookies,
            callback=self.parse_application_details,
            cb_kwargs={
                "council_name": council_name,
                "config": config,
                "app_id": app_id,
            },
            dont_filter=True,
            meta={
                "council_name": council_name,
                "waf_token": waf_token,
            },
        )

    def parse_application_details(self, response, council_name: str, config: Dict[str, str], app_id: str):
        """Parse application details page and yield items."""
        self.logger.debug(f"Parsing application details for {council_name}: app_id={app_id}")
        self.stats["applications_found"] += 1

        # Create application item
        app_item = PlanningApplicationItem()

        # Core identification
        app_item["application_reference"] = self._extract_field(response, ["Application Reference Number", "Reference"])
        app_item["application_url"] = config["url"]
        app_item["council_name"] = council_name

        # Location details
        app_item["site_address"] = self._extract_field(response, ["Location", "Site Address", "Address"])
        app_item["ward"] = self._extract_field(response, ["Ward"])
        app_item["parish"] = self._extract_field(response, ["Parish", "Parish / Community"])

        # Extract postcode from address
        if app_item.get("site_address"):
            app_item["postcode"] = self._extract_postcode(app_item["site_address"])

        # Application details
        app_item["application_type"] = self._extract_field(response, ["Application Type", "Type"])
        app_item["proposal"] = self._extract_field(response, ["Proposal", "Description"])
        app_item["status"] = self._extract_field(response, ["Application Status", "Status"])
        app_item["decision"] = self._extract_field(response, ["Decision", "Decision:"])

        # People
        app_item["applicant_name"] = self._extract_field(response, ["Applicant", "Applicant Name"])
        app_item["agent_name"] = self._extract_field(response, ["Agent", "Agent Name"])
        app_item["case_officer"] = self._extract_field(response, ["Officer", "Case Officer"])

        # Dates
        app_item["registration_date"] = self._extract_field(response, ["Received Date", "Valid Date", "Registration Date"])
        app_item["valid_from"] = self._extract_field(response, ["Valid Date"])
        app_item["decision_date"] = self._extract_field(response, ["Decision Issued Date", "Decision Date"])

        # Internal tracking
        app_item["_portal_framework"] = "fa_search"
        app_item["_scraped_at"] = datetime.utcnow().isoformat()

        yield app_item

        # Extract documents
        yield from self._extract_documents(response, app_item["application_reference"], council_name)

    def _extract_field(self, response, labels: list) -> Optional[str]:
        """Extract a field value from the detail page by label."""
        for label in labels:
            # FA_SEARCH typically uses: <div><div><strong>Label</strong></div><div>Value</div></div>
            selectors = [
                f'//div[div/strong[contains(text(), "{label}")]]/div[2]/text()',
                f'//td[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//th[contains(text(), "{label}")]/following-sibling::td/text()',
                f'//span[contains(text(), "{label}")]/following::span/text()',
                f'//label[contains(text(), "{label}")]/following-sibling::*/text()',
            ]

            for selector in selectors:
                values = response.xpath(selector).getall()
                for value in values:
                    cleaned = value.strip()
                    if cleaned and cleaned.lower() not in ["n/a", "none", "-", ""]:
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

    def _extract_documents(self, response, app_ref: Optional[str], council_name: str):
        """Extract document links from application detail page."""
        # Look for document links
        doc_links = (
            response.xpath("//a[contains(@href, '.pdf')]/@href").getall()
            or response.xpath("//a[contains(@href, 'document')]/@href").getall()
            or response.xpath("//a[contains(@href, 'download')]/@href").getall()
        )

        for doc_url in doc_links:
            doc_url = response.urljoin(doc_url)
            self.stats["documents_found"] += 1

            yield DocumentItem(
                application_reference=app_ref or "unknown",
                council_name=council_name,
                document_url=doc_url,
                filename=self._extract_filename_from_url(doc_url),
                source_url=response.url,
                _portal_framework="fa_search",
                _scraped_at=datetime.utcnow().isoformat(),
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

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("FA_SEARCH SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
