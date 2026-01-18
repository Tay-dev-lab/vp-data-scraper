"""
ARCUS (Salesforce) Spider - scrapes UK planning portals using the Salesforce Aura framework.

This spider handles Salesforce Lightning Web Component (LWC) based planning portals
that use the Aura API for data fetching.

Supports: Haringey (London borough)

Flow:
1. Load initial page to extract fwuid context token
2. POST to Aura API endpoint with search parameters
3. Parse JSON response for application records
4. Yield application items (documents loaded via JavaScript, may need separate handling)
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin

import scrapy
from scrapy_playwright.page import PageMethod

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_arcus_urls


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


class ArcusSpider(scrapy.Spider):
    """
    Spider for ARCUS (Salesforce Aura) based planning portals.

    Uses Salesforce Aura API with JSON-RPC style requests.

    Usage:
        scrapy crawl arcus -a region=london -a days_back=30
        scrapy crawl arcus -a council=haringey -a days_back=30
        scrapy crawl arcus -a council=haringey -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "arcus"

    @classmethod
    def _build_custom_settings(cls):
        """Build custom settings with proxy config."""
        proxy_config = _get_playwright_proxy_config()

        settings = {
            # Playwright settings for browser-based scraping (needed for fwuid extraction)
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
            "DOWNLOAD_DELAY": 2.0,
            "COOKIES_ENABLED": True,
            "RETRY_ENABLED": True,
            "RETRY_TIMES": 3,
            "AUTOTHROTTLE_ENABLED": True,
            "AUTOTHROTTLE_START_DELAY": 2.0,
            "AUTOTHROTTLE_MAX_DELAY": 10.0,
            "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
            "DOWNLOAD_TIMEOUT": 120,
            # Handle Salesforce error codes
            "HTTPERROR_ALLOWED_CODES": [403],
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
        self.portal_urls = get_arcus_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No ARCUS portals found for region='{region}', council='{council}'. "
                "Valid councils: haringey"
            )

        # Calculate date range (ARCUS uses YYYY-MM-DD format)
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

        # Build allowed domains from URLs
        self.allowed_domains = list(
            {urlparse(config["url"]).netloc.split(":")[0] for config in self.portal_urls.values()}
        )

        # Store fwuid tokens per domain
        self.fwuid_tokens: Dict[str, str] = {}

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
        self.logger.info("ARCUS SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date_display} to {self.end_date_display}")
        self.logger.info(f"  ARCUS Date Format: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 2.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests to extract fwuid context."""
        for council_name, config in self.portal_urls.items():
            portal_url = config["url"]
            self.logger.info(f"Starting fwuid extraction for council: {council_name}")

            yield scrapy.Request(
                url=portal_url,
                callback=self.extract_fwuid,
                cb_kwargs={"council_name": council_name, "config": config},
                dont_filter=True,
                meta={
                    "council_name": council_name,
                    "playwright": True,
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("wait_for_timeout", 5000),
                    ],
                },
            )

    async def extract_fwuid(self, response, council_name: str, config: Dict[str, str]):
        """Extract fwuid context from the page using Playwright."""
        page = response.meta.get("playwright_page")
        domain = urlparse(config["url"]).netloc

        if not page:
            self.logger.error(f"No Playwright page for {council_name}")
            return

        try:
            # Get page content to extract fwuid from JavaScript
            content = await page.content()

            # Look for fwuid in the page content
            # It's typically in the aura.context object
            fwuid = None

            # Try to find fwuid in various patterns
            fwuid_patterns = [
                r'"fwuid"\s*:\s*"([^"]+)"',
                r"fwuid['\"]?\s*:\s*['\"]([^'\"]+)['\"]",
                r'auraConfig[^}]*fwuid[^}]*"([^"]+)"',
            ]

            for pattern in fwuid_patterns:
                match = re.search(pattern, content)
                if match:
                    fwuid = match.group(1)
                    self.logger.info(f"Found fwuid for {council_name}: {fwuid[:50]}...")
                    break

            # Get cookies for the request
            cookies = await page.context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}

            # Close the page
            await page.close()

            if not fwuid:
                self.logger.warning(f"Could not extract fwuid for {council_name}, using default")
                # Use a default fwuid that might work
                fwuid = "Zm9LbDZETkxUclI3TmZfamRYSmpzUWg5TGxiTHU3MEQ5RnBMM0VzVXc1cmcxMS4zMjc2OC4w"

            self.fwuid_tokens[domain] = fwuid

            # Now submit the search - yield each request
            for request in self._submit_aura_search(council_name, config, fwuid, cookie_dict):
                yield request

        except Exception as e:
            self.logger.error(f"Error extracting fwuid for {council_name}: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            if page:
                await page.close()

    def _submit_aura_search(
        self,
        council_name: str,
        config: Dict[str, str],
        fwuid: str,
        cookies: Dict[str, str],
    ):
        """Submit Aura API search request."""
        aura_endpoint = config.get("aura_endpoint", f"{config['url'].rstrip('/')}/s/sfsites/aura")
        register_name = config.get("register_name", "Arcus_BE_Public_Register")
        domain = urlparse(config["url"]).netloc

        self.logger.info(f"Submitting Aura search for {council_name}: {self.start_date} to {self.end_date}")

        # Build the Aura API request
        message = {
            "actions": [{
                "id": "89;a",
                "descriptor": "aura://ApexActionController/ACTION$execute",
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "namespace": "arcuscommunity",
                    "classname": "PR_SearchService",
                    "method": "search",
                    "params": {
                        "request": {
                            "registerName": register_name,
                            "searchType": "advanced",
                            "searchName": "Planning_Applications",
                            "advancedSearchName": "PA_ADV_All",
                            "searchFilters": [
                                {"fieldName": "arcusbuiltenv__Site_Address__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_SiteAddress"},
                                {"fieldName": "arcusbuiltenv__Proposal__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_Proposal"},
                                {"fieldName": "arcusbuiltenv__Status__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_ApplicationStatus"},
                                {"fieldName": "Name", "fieldValue": "", "fieldDeveloperName": "PA_ADV_RecordType"},
                                {"fieldName": "arcusbuiltenv__Type__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_ApplicationType"},
                                {"fieldName": "arcusbuiltenv__Valid_Date__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_DateValidFrom"},
                                {"fieldName": "arcusbuiltenv__Valid_Date__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_DateValidTo"},
                                {"fieldName": "arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c", "fieldValue": self.start_date, "fieldDeveloperName": "PA_ADV_DecisionNoticeSentDateFrom"},
                                {"fieldName": "arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c", "fieldValue": self.end_date, "fieldDeveloperName": "PA_ADV_DecisionNoticeSentDateTo"},
                                {"fieldName": "arcusbuiltenv__Parishes__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_Parish"},
                                {"fieldName": "arcusbuiltenv__Wards__c", "fieldValue": "", "fieldDeveloperName": "PA_ADV_Ward"},
                            ],
                        },
                    },
                    "cacheable": False,
                    "isContinuation": False,
                },
            }],
        }

        aura_context = {
            "mode": "PROD",
            "fwuid": fwuid,
            "app": "siteforce:communityApp",
            "loaded": {
                "APPLICATION@markup://siteforce:communityApp": "1232_i1u-juBSAcYeYnyHhRNT-Q"
            },
            "dn": [],
            "globals": {"srcdoc": True},
            "uad": True,
        }

        # Build form data
        formdata = {
            "message": json.dumps(message),
            "aura.context": json.dumps(aura_context),
            "aura.pageURI": f"/s/register-view?c__r={register_name}",
            "aura.token": "null",
        }

        # Build headers
        headers = {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Origin": f"https://{domain}",
            "Referer": config["url"],
            "X-SFDC-LDS-Endpoints": "ApexActionController.execute:PR_SearchService.search",
        }

        yield scrapy.FormRequest(
            url=aura_endpoint,
            formdata=formdata,
            headers=headers,
            cookies=cookies,
            callback=self.parse_aura_response,
            cb_kwargs={
                "council_name": council_name,
                "config": config,
            },
            dont_filter=True,
            meta={
                "council_name": council_name,
            },
        )

    def parse_aura_response(self, response, council_name: str, config: Dict[str, str]):
        """Parse Aura API response and yield application items."""
        self.logger.info(f"Parsing Aura response for {council_name} (status: {response.status})")
        self.stats["councils_processed"] += 1

        if response.status != 200:
            self.logger.error(f"Aura API request failed for {council_name}: status {response.status}")
            self.logger.error(f"Response: {response.text[:500]}")
            return

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON for {council_name}: {e}")
            self.logger.error(f"Response: {response.text[:500]}")
            return

        # Extract records from the nested response structure
        records = []
        try:
            if "actions" in data and len(data["actions"]) > 0:
                action = data["actions"][0]
                if "returnValue" in action:
                    return_value = action["returnValue"]
                    if isinstance(return_value, dict) and "returnValue" in return_value:
                        inner_value = return_value["returnValue"]
                        if isinstance(inner_value, dict) and "records" in inner_value:
                            records = inner_value["records"]
        except (KeyError, IndexError, TypeError) as e:
            self.logger.error(f"Error extracting records for {council_name}: {e}")
            self.logger.debug(f"Response structure: {json.dumps(data)[:1000]}")
            return

        self.logger.info(f"Found {len(records)} applications for {council_name}")

        # Yield application items
        for record in records:
            self.stats["applications_found"] += 1
            yield self._create_application_item(record, council_name, config)

    def _create_application_item(
        self, record: Dict[str, Any], council_name: str, config: Dict[str, str]
    ) -> PlanningApplicationItem:
        """Create a PlanningApplicationItem from ARCUS record data."""
        item = PlanningApplicationItem()

        # Core identification
        item["application_reference"] = record.get("Name")
        item["application_url"] = config["url"]
        item["council_name"] = council_name

        # Location details
        item["site_address"] = record.get("arcusbuiltenv__Site_Address__c")

        # Extract postcode from address
        if item.get("site_address"):
            item["postcode"] = self._extract_postcode(item["site_address"])

        item["ward"] = record.get("arcusbuiltenv__Wards__c")
        item["parish"] = record.get("arcusbuiltenv__Parishes__c")

        # Application details
        item["application_type"] = record.get("arcusbuiltenv__Type__c")
        item["proposal"] = record.get("arcusbuiltenv__Proposal__c")
        item["status"] = record.get("arcusbuiltenv__Status__c")
        item["decision"] = record.get("Current_Decision_Final__c") or record.get("arcusbuiltenv__Decision__c")

        # Dates
        valid_date = record.get("arcusbuiltenv__Valid_Date__c")
        if valid_date:
            item["valid_from"] = self._format_date(valid_date)
            item["registration_date"] = self._format_date(valid_date)

        decision_date = record.get("arcusbuiltenv__Decision_Notice_Sent_Date_Manual__c")
        if decision_date:
            item["decision_date"] = self._format_date(decision_date)

        # Internal tracking
        item["_portal_framework"] = "arcus"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract postcode from address string."""
        if not address:
            return None

        pattern = r'[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}'
        match = re.search(pattern, address.upper())
        return match.group(0) if match else None

    def _format_date(self, date_str: Optional[str]) -> Optional[str]:
        """Format ISO date to DD/MM/YYYY for consistency."""
        if not date_str:
            return None
        try:
            # Handle ISO format (YYYY-MM-DD)
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return date_str

    def closed(self, reason):
        """Log final statistics when spider closes."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("ARCUS SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
