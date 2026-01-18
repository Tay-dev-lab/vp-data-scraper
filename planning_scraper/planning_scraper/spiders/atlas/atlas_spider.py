"""
Atlas Spider - scrapes RBKC planning portal (atlas.rbkc.gov.uk).

Atlas is a SolidStart-based SPA that wraps Idox Uniform backend.
Uses Playwright to navigate the SPA and intercept API responses.

Flow:
1. Navigate to portal and search for applications
2. For each application, fetch case details via server function
3. Navigate to application page to get documents
4. Yield application and document items

Target URL: https://atlas.rbkc.gov.uk/planningsearch/
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, quote, unquote, urlparse, parse_qs

import scrapy
from scrapy_playwright.page import PageMethod

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_atlas_urls


class AtlasSpider(scrapy.Spider):
    """
    Spider for Atlas-based planning portals (currently RBKC).

    Uses Playwright to navigate the SPA and intercept server function responses.

    Usage:
        scrapy crawl atlas -a council=rbkc -a days_back=30
        scrapy crawl atlas -a council=rbkc -a start_date=01/01/2025 -a end_date=31/01/2025
    """

    name = "atlas"

    # Base URLs
    PORTAL_BASE = "https://atlas.rbkc.gov.uk/planningsearch/"
    SERVER_ENDPOINT = "https://atlas.rbkc.gov.uk/planningsearch/_server/"

    custom_settings = {
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
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 90000,  # 90 seconds for SPA
        # Conservative rate limiting
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
        # Disable proxy middleware - Playwright handles its own requests
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
        self.council = council or "rbkc"  # Default to RBKC

        # Get URLs based on region/council filter
        self.portal_urls = get_atlas_urls(region=self.region, council=self.council)

        if not self.portal_urls:
            raise ValueError(
                f"No Atlas portals found for region='{region}', council='{council}'. "
                "Valid councils: rbkc"
            )

        # Calculate date range
        if start_date and end_date:
            self.start_date = datetime.strptime(start_date, "%d/%m/%Y")
            self.end_date = datetime.strptime(end_date, "%d/%m/%Y")
            self.start_date_display = start_date
            self.end_date_display = end_date
        else:
            self.end_date = datetime.now()
            self.start_date = self.end_date - timedelta(days=int(days_back))
            self.start_date_display = self.start_date.strftime("%d/%m/%Y")
            self.end_date_display = self.end_date.strftime("%d/%m/%Y")

        # Track discovered applications
        self.discovered_apps: List[str] = []

        # Stats
        self.stats = {
            "councils_processed": 0,
            "applications_found": 0,
            "documents_found": 0,
        }

        self._log_startup_config()

    def _log_startup_config(self):
        """Log clear startup configuration."""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("ATLAS SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date_display} to {self.end_date_display}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        for council_name in self.portal_urls.keys():
            self.logger.info(f"    - {council_name}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 2.0)}s")
        self.logger.info("=" * 60)
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests to the Atlas portal."""
        for council_name, config in self.portal_urls.items():
            portal_url = config["url"]

            self.logger.info(f"Starting requests for council: {council_name}")

            # Strategy: Search for recent applications by reference pattern
            # RBKC uses PP/YY/NNNNN format (e.g., PP/24/00001)
            # We'll search for each year/month combination in the date range

            search_terms = self._generate_search_terms()

            for search_term in search_terms:
                yield scrapy.Request(
                    url=portal_url,
                    callback=self.parse_with_search,
                    cb_kwargs={
                        "council_name": council_name,
                        "search_term": search_term,
                    },
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_load_state", "domcontentloaded"),
                            PageMethod("wait_for_timeout", 2000),
                        ],
                    },
                    dont_filter=True,
                )

    def _generate_search_terms(self) -> List[str]:
        """Generate search terms based on date range.

        RBKC uses reference format: PP/YY/NNNNN
        We search by year prefix to find applications.
        """
        search_terms = []

        # Get unique years in the date range
        current = self.start_date
        years_seen = set()

        while current <= self.end_date:
            year_short = current.strftime("%y")  # 24 for 2024
            if year_short not in years_seen:
                years_seen.add(year_short)
                # Search for planning permission applications
                search_terms.append(f"PP/{year_short}/")

            current += timedelta(days=30)

        return search_terms

    async def parse_with_search(self, response, council_name: str, search_term: str):
        """Parse the portal page and perform a search."""
        page = response.meta.get("playwright_page")

        self.logger.info(f"Performing search for: {search_term} on {council_name}")

        if not page:
            self.logger.error("No Playwright page available")
            return

        try:
            # Find and fill the search input
            search_input = await page.query_selector('#searchInput')
            if not search_input:
                self.logger.warning("Search input not found")
                await page.close()
                return

            # Type the search term to trigger autocomplete
            await search_input.fill(search_term)
            await page.wait_for_timeout(2000)  # Wait for autocomplete

            # Collect all autocomplete results
            autocomplete_items = await page.query_selector_all('div:has-text("Case reference:")')

            app_refs = []
            for item in autocomplete_items:
                text = await item.text_content()
                if text and "Case reference:" in text:
                    # Extract the reference number
                    match = re.search(r'PP/\d{2}/\d+', text)
                    if match:
                        app_ref = match.group(0)
                        if app_ref not in self.discovered_apps:
                            self.discovered_apps.append(app_ref)
                            app_refs.append(app_ref)

            self.logger.info(f"Found {len(app_refs)} new applications from search '{search_term}'")

            # Close the search page
            await page.close()

            # Yield requests for each application
            for app_ref in app_refs:
                case_url = f"{self.PORTAL_BASE}cases/{app_ref}"

                yield scrapy.Request(
                    url=case_url,
                    callback=self.parse_case_page,
                    cb_kwargs={
                        "council_name": council_name,
                        "app_ref": app_ref,
                    },
                    meta={
                        "playwright": True,
                        "playwright_include_page": True,
                        "playwright_page_methods": [
                            PageMethod("wait_for_load_state", "domcontentloaded"),
                            PageMethod("wait_for_timeout", 3000),
                        ],
                    },
                    dont_filter=True,
                )

        except Exception as e:
            self.logger.error(f"Error during search: {e}")
            if page:
                await page.close()

    async def parse_case_page(self, response, council_name: str, app_ref: str):
        """Parse a case detail page."""
        page = response.meta.get("playwright_page")

        self.logger.info(f"Parsing case page for: {app_ref}")

        if not page:
            self.logger.error("No Playwright page available")
            return

        try:
            # Extract case data from the page
            # The data is loaded via server function but rendered in the DOM
            case_data = await self._extract_case_data(page, app_ref)

            if case_data:
                self.stats["applications_found"] += 1

                # Create application item
                app_item = self._create_application_item(case_data, council_name, response.url)

                # Check if application date is within our range
                if self._is_in_date_range(case_data):
                    yield app_item

                    # Look for documents
                    documents = await self._extract_documents(page, app_ref)

                    for doc in documents:
                        self.stats["documents_found"] += 1
                        yield self._create_document_item(
                            doc, council_name, app_ref, response.url
                        )
                else:
                    self.logger.debug(f"Application {app_ref} outside date range, skipping")

            await page.close()

        except Exception as e:
            self.logger.error(f"Error parsing case page for {app_ref}: {e}")
            if page:
                await page.close()

    async def _extract_case_data(self, page, app_ref: str) -> Optional[Dict[str, Any]]:
        """Extract case data from the visible DOM elements."""
        try:
            case_data = {"caseReference": app_ref}

            # Wait for content to render
            await page.wait_for_timeout(2000)

            # Extract data using JavaScript evaluation on visible DOM
            dom_data = await page.evaluate('''() => {
                const data = {};

                // Get all text content from the page
                const pageText = document.body.innerText || '';

                // Extract "Proposed development:" section
                const devMatch = pageText.match(/Proposed development:\\s*([\\s\\S]*?)(?=(?:Location\\s|Application type|Ward|Applicant|Agent|Case officer|$))/i);
                if (devMatch) {
                    let desc = devMatch[1].trim();
                    // Clean up: remove "Location" prefix if it got included
                    desc = desc.replace(/^Location\\s+[^\\n]+\\n/i, '').trim();
                    data.descriptionShort = desc.slice(0, 500);
                }

                // Extract Application type
                const typeMatch = pageText.match(/Application type[:\\s]*([^\\n]+)/i);
                if (typeMatch) data.applicationType = typeMatch[1].trim();

                // Extract Ward
                const wardMatch = pageText.match(/Ward[:\\s]*([^\\n]+)/i);
                if (wardMatch && wardMatch[1].trim() !== ':') data.ward = wardMatch[1].trim();

                // Extract Address (usually after "Site address" or near the top)
                const addrMatch = pageText.match(/Site address[:\\s]*([^\\n]+)/i);
                if (addrMatch) data.address = addrMatch[1].trim();

                // Alternative: Look for location on map - address might be in title or near map
                const mapAddrMatch = pageText.match(/Location\\s+([^\\n]+)/i);
                if (!data.address && mapAddrMatch) data.address = mapAddrMatch[1].trim();

                // Extract Applicant (avoid matching "View applicant detail" links)
                const applicantMatch = pageText.match(/Applicant\\s+name[:\\s]*([^\\n]+)/i);
                if (applicantMatch && !applicantMatch[1].toLowerCase().includes('detail')) {
                    data.applicantName = applicantMatch[1].trim();
                }

                // Extract Agent
                const agentMatch = pageText.match(/Agent[:\\s]*([^\\n]+)/i);
                if (agentMatch) data.agentName = agentMatch[1].trim();

                // Extract Case officer
                const officerMatch = pageText.match(/Case officer[:\\s]*([^\\n]+)/i);
                if (officerMatch) data.caseOfficer = officerMatch[1].trim();

                // Extract dates from the timeline
                // "Submitted\\n21 Nov 2025" format
                const submittedMatch = pageText.match(/Submitted\\s+(\\d{1,2} \\w+ \\d{4})/);
                if (submittedMatch) data.dateReceived = submittedMatch[1];

                const consultMatch = pageText.match(/Consultation From\\s+(\\d{1,2} \\w+ \\d{4})/);
                if (consultMatch) data.dateConsultation = consultMatch[1];

                // Extract status (Open, Decided, etc.)
                const statusEl = document.querySelector('[class*="status"], [class*="pill"]');
                if (statusEl) {
                    const statusText = statusEl.innerText.trim();
                    if (statusText && statusText.length < 50) {
                        data.applicationStatus = statusText;
                    }
                }

                // Alternative status detection
                if (!data.applicationStatus) {
                    if (pageText.includes('Open')) data.applicationStatus = 'Open';
                    else if (pageText.includes('Decided')) data.applicationStatus = 'Decided';
                    else if (pageText.includes('Withdrawn')) data.applicationStatus = 'Withdrawn';
                }

                return data;
            }''')

            if dom_data:
                case_data.update(dom_data)

            # Clean up extracted data
            for key in list(case_data.keys()):
                value = case_data.get(key)
                if isinstance(value, str):
                    # Remove extra whitespace
                    case_data[key] = ' '.join(value.split())
                    # Remove if just punctuation or empty
                    if not case_data[key] or case_data[key] in [':', '-', 'N/A', ':']:
                        del case_data[key]

            self.logger.debug(f"Extracted case data for {app_ref}: {list(case_data.keys())}")
            return case_data

        except Exception as e:
            self.logger.error(f"Error extracting case data: {e}")
            return {"caseReference": app_ref}

    async def _extract_documents(self, page, app_ref: str) -> List[Dict[str, Any]]:
        """Extract document links from the page."""
        documents = []

        try:
            # Look for a "See documents" or "Documents" tab
            doc_buttons = await page.query_selector_all('button:has-text("document"), a:has-text("document")')

            for btn in doc_buttons:
                text = await btn.text_content()
                if 'document' in text.lower():
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    break

            # Look for document links
            doc_links = await page.query_selector_all('a[href*="pdf"], a[href*="document"], a[href*="download"]')

            for link in doc_links:
                href = await link.get_attribute('href')
                text = await link.text_content()

                if href:
                    documents.append({
                        "url": href,
                        "filename": text.strip() if text else self._extract_filename_from_url(href),
                    })

            # Also look for document table rows
            doc_rows = await page.query_selector_all('tr:has(a[href*="pdf"]), tr:has(a[href*="document"])')

            for row in doc_rows:
                link = await row.query_selector('a')
                if link:
                    href = await link.get_attribute('href')
                    text = await link.text_content()

                    # Try to get document type from other columns
                    cells = await row.query_selector_all('td')
                    doc_type = ""
                    if len(cells) > 1:
                        type_text = await cells[1].text_content()
                        if type_text:
                            doc_type = type_text.strip()

                    if href and href not in [d["url"] for d in documents]:
                        documents.append({
                            "url": href,
                            "filename": text.strip() if text else self._extract_filename_from_url(href),
                            "document_type": doc_type,
                        })

        except Exception as e:
            self.logger.error(f"Error extracting documents: {e}")

        return documents

    def _is_in_date_range(self, case_data: Dict[str, Any]) -> bool:
        """Check if application date is within our date range."""
        # Try different date fields
        date_fields = ["dateReceived", "dateRegistered", "dateConsultation"]

        for field in date_fields:
            date_str = case_data.get(field)
            if date_str:
                try:
                    # Try ISO format first (2024-07-11T00:00:00.000Z)
                    date = datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
                    date = date.replace(tzinfo=None)
                    return self.start_date <= date <= self.end_date
                except (ValueError, AttributeError):
                    pass

                try:
                    # Try "21 Nov 2025" format
                    date = datetime.strptime(date_str, "%d %b %Y")
                    return self.start_date <= date <= self.end_date
                except (ValueError, AttributeError):
                    pass

                try:
                    # Try DD/MM/YYYY format
                    date = datetime.strptime(date_str, "%d/%m/%Y")
                    return self.start_date <= date <= self.end_date
                except (ValueError, AttributeError):
                    pass

        # If no valid date found, include it (conservative approach)
        return True

    def _create_application_item(
        self, case_data: Dict[str, Any], council_name: str, url: str
    ) -> PlanningApplicationItem:
        """Create a PlanningApplicationItem from case data."""
        item = PlanningApplicationItem()

        # Core identification
        item["application_reference"] = case_data.get("caseReference")
        item["application_url"] = url
        item["council_name"] = council_name

        # Location
        item["site_address"] = case_data.get("address")
        item["ward"] = case_data.get("ward")
        item["postcode"] = self._extract_postcode(case_data.get("address", ""))

        # Application details
        item["application_type"] = case_data.get("applicationType")
        item["proposal"] = case_data.get("descriptionFull") or case_data.get("descriptionShort")
        item["status"] = case_data.get("applicationStatus")
        item["decision"] = case_data.get("decisionName")

        # Dates
        item["registration_date"] = self._format_date(case_data.get("dateRegistered"))
        item["decision_date"] = self._format_date(case_data.get("dateDecision"))

        # People
        applicant = case_data.get("applicantName") or case_data.get("applicantCompanyName")
        if applicant:
            item["applicant_name"] = applicant

        officer = case_data.get("planningDeptContactOfficer")
        if officer:
            item["case_officer"] = officer

        # Location data
        if case_data.get("latitude") and case_data.get("longitude"):
            try:
                item["latitude"] = float(case_data["latitude"])
                item["longitude"] = float(case_data["longitude"])
            except (ValueError, TypeError):
                pass

        # Conservation area
        conservation = case_data.get("conservationArea")
        if conservation and conservation != "N/A":
            item["conservation_area"] = conservation

        # Internal tracking
        item["_portal_framework"] = "atlas"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def _create_document_item(
        self, doc: Dict[str, Any], council_name: str, app_ref: str, source_url: str
    ) -> DocumentItem:
        """Create a DocumentItem from document data."""
        item = DocumentItem()

        # Source information
        doc_url = doc.get("url", "")
        if not doc_url.startswith("http"):
            doc_url = urljoin(self.PORTAL_BASE, doc_url)

        item["document_url"] = doc_url
        item["source_url"] = source_url
        item["filename"] = doc.get("filename", self._extract_filename_from_url(doc_url))

        # Parent application reference
        item["application_reference"] = app_ref
        item["council_name"] = council_name

        # Document type
        item["document_type"] = doc.get("document_type", "document")

        # Internal tracking
        item["_portal_framework"] = "atlas"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item

    def _format_date(self, date_str: Optional[str]) -> Optional[str]:
        """Format ISO date to DD/MM/YYYY for consistency."""
        if not date_str:
            return None
        try:
            # Parse ISO format (2024-07-11T00:00:00.000Z)
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
            return dt.strftime("%d/%m/%Y")
        except (ValueError, AttributeError):
            return date_str

    def _extract_postcode(self, address: str) -> Optional[str]:
        """Extract postcode from address string."""
        if not address:
            return None

        # UK postcode pattern
        pattern = r'[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}'
        match = re.search(pattern, address.upper())
        return match.group(0) if match else None

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
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
        self.logger.info("ATLAS SPIDER COMPLETED")
        self.logger.info("=" * 60)
        self.logger.info(f"  Reason: {reason}")
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Council: {self.council or 'all'}")
        self.logger.info(f"  Councils Processed: {self.stats['councils_processed']}")
        self.logger.info(f"  Applications Found: {self.stats['applications_found']}")
        self.logger.info(f"  Documents Found: {self.stats['documents_found']}")
        self.logger.info("=" * 60)
        self.logger.info("")
