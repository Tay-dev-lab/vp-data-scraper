"""
IDOX Spider - scrapes UK planning portals using the IDOX framework.

Flow:
1. Search form → Submit date-based search
2. Search results → Extract application links
3. Application details → Parse metadata, follow tabs
4. Further info tab → Get application type, ward, parish
5. Documents tab → Find and yield PDF documents
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urljoin

import scrapy
from scrapy.loader import ItemLoader

from ...items.application import PlanningApplicationItem
from ...items.document import DocumentItem
from ...config.portals import get_active_idox_urls


class IdoxSpider(scrapy.Spider):
    """
    Spider for IDOX-based planning portals.

    Targets residential/householder applications and extracts
    planning drawing documents for PDF download.

    Usage:
        scrapy crawl idox -a days_back=30
        scrapy crawl idox -a start_date=01/01/2025 -a end_date=31/01/2025
        scrapy crawl idox -a region=london -a days_back=30  # London boroughs only
    """

    name = "idox"

    custom_settings = {
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "DOWNLOAD_DELAY": 1.0,
        "COOKIES_ENABLED": True,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.0,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 2.0,
        "DOWNLOAD_TIMEOUT": 60,
    }

    def __init__(
        self,
        days_back: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        region: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Store region filter
        self.region = region

        # Get URLs based on region filter
        self.portal_urls = get_active_idox_urls(region=self.region)

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
            {urlparse(url).netloc.split(":")[0] for url in self.portal_urls}
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
        self.logger.info("IDOX SPIDER CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"  Region: {self.region or 'all'}")
        self.logger.info(f"  Date Range: {self.start_date} to {self.end_date}")
        self.logger.info(f"  Target Councils: {len(self.portal_urls)}")
        self.logger.info(f"  Concurrent Requests: {self.custom_settings.get('CONCURRENT_REQUESTS', 8)}")
        self.logger.info(f"  Download Delay: {self.custom_settings.get('DOWNLOAD_DELAY', 1.0)}s")
        self.logger.info(f"  Autothrottle: ENABLED")
        self.logger.info("=" * 60)
        self.logger.info("")
        self.logger.info("Target councils:")
        for i, url in enumerate(self.portal_urls[:5], 1):
            council = self._extract_council_name(url)
            self.logger.info(f"  {i}. {council}")
        if len(self.portal_urls) > 5:
            self.logger.info(f"  ... and {len(self.portal_urls) - 5} more")
        self.logger.info("")

    def start_requests(self):
        """Generate initial requests for each IDOX portal."""
        for url in self.portal_urls:
            council_name = self._extract_council_name(url)
            self.logger.info(f"Starting scrape for council: {council_name}")

            yield scrapy.Request(
                url=url,
                callback=self.parse_search_form,
                cb_kwargs={"council_name": council_name, "base_url": url},
                dont_filter=True,
                meta={"council_name": council_name},
            )

    def _extract_council_name(self, url: str) -> str:
        """Extract council name from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc

        # Remove common prefixes and suffixes
        for prefix in [
            "planning.",
            "publicaccess.",
            "pa.",
            "idoxpa.",
            "eplanning.",
            "planningpublicaccess.",
            "development.",
            "searchapplications.",
        ]:
            if domain.startswith(prefix):
                domain = domain[len(prefix) :]

        for suffix in [".gov.uk", ".gov", ".co.uk", ".org.uk", ".wales"]:
            if domain.endswith(suffix):
                domain = domain[: -len(suffix)]

        return domain.replace(".", "_").replace("-", "_")

    def parse_search_form(self, response, council_name: str, base_url: str):
        """Parse the search form and submit a date-based search."""
        # Get CSRF token if present
        csrf_token = response.css('input[name="_csrf"]::attr(value)').get()

        # Build form data
        formdata = {
            "searchType": "Application",
            "action": "search",
            "caseAddressType": "Application",
            "searchCriteria.decision": "Decision",
            "date(applicationDecisionStart)": self.start_date,
            "date(applicationDecisionEnd)": self.end_date,
        }

        if csrf_token:
            formdata["_csrf"] = csrf_token

        # Clean form data
        formdata = {k: str(v) if v is not None else "" for k, v in formdata.items()}

        # Get search results URL
        search_url = response.urljoin("advancedSearchResults.do?action=firstPage")

        self.logger.debug(f"Submitting search form for {council_name}")

        yield scrapy.FormRequest(
            url=search_url,
            formdata=formdata,
            callback=self.parse_search_results,
            cb_kwargs={"council_name": council_name, "base_url": base_url},
            dont_filter=True,
            meta={"council_name": council_name},
        )

    def parse_search_results(self, response, council_name: str, base_url: str):
        """Parse search results page and follow application links."""
        results = response.css("li.searchresult")

        if results:
            self.logger.info(
                f"Found {len(results)} results for {council_name} on current page"
            )
        else:
            self.logger.debug(f"No results found for {council_name}")
            return

        for result in results:
            app_url = result.css("a::attr(href)").get()
            if not app_url:
                continue

            self.stats["applications_found"] += 1

            # Extract basic info from search results
            app_data = {
                "council_name": council_name,
                "application_reference": result.css("p.metaInfo::text").re_first(
                    r"Ref\. No:\s*([^\n]*)"
                ),
                "proposal": result.css("p.description::text").get("").strip(),
                "status": result.css("p.metaInfo::text").re_first(r"Status:\s*([^\n]*)"),
                "application_url": response.urljoin(app_url),
            }

            # Clean values
            app_data = {
                k: v.strip() if isinstance(v, str) else v for k, v in app_data.items()
            }

            yield scrapy.Request(
                url=response.urljoin(app_url),
                callback=self.parse_application_summary,
                cb_kwargs={
                    "app_data": app_data,
                    "council_name": council_name,
                    "base_url": base_url,
                },
                meta={"council_name": council_name},
            )

        # Follow pagination
        next_page = response.css("a.next::attr(href)").get()
        if next_page:
            self.logger.debug(f"Following next page for {council_name}")
            yield scrapy.Request(
                url=response.urljoin(next_page),
                callback=self.parse_search_results,
                cb_kwargs={"council_name": council_name, "base_url": base_url},
                meta={"council_name": council_name},
            )

    def parse_application_summary(
        self, response, app_data: Dict[str, Any], council_name: str, base_url: str
    ):
        """Parse the application summary page."""
        # Field mappings for summary table
        field_mapping = {
            "Reference": "application_reference",
            "Application Received": "registration_date",
            "Application Validated": "valid_from",
            "Address": "site_address",
            "Proposal": "proposal",
            "Status": "status",
            "Decision": "decision",
            "Decision Issued Date": "decision_date",
            "Appeal Status": "appeal_submitted",
            "Appeal Decision": "appeal_decision",
        }

        # Extract status from span if present
        status_span = response.xpath(
            "//span[@class='caseDetailsStatus']/text()"
        ).get()
        if status_span:
            app_data["status"] = status_span.strip()

        # Parse summary table
        for row in response.xpath("//table[@id='simpleDetailsTable']//tr"):
            field_name = row.xpath("normalize-space(.//th/text())").get("")

            if field_name == "Status":
                field_value = row.xpath("normalize-space(.//td//span/text())").get("")
                if not field_value:
                    field_value = row.xpath("normalize-space(.//td/text())").get("")
            else:
                field_value = row.xpath("normalize-space(.//td/text())").get("")

            if field_name and field_value and field_value not in [
                "Not Available",
                "Unknown",
            ]:
                if field_name in field_mapping:
                    app_data[field_mapping[field_name]] = field_value

        # Follow Further Information tab - try multiple selectors
        further_info_url = (
            response.xpath("//a[@id='subtab_details']/@href").get()
            or response.xpath("//a[contains(@href, 'activeTab=details')]/@href").get()
            or response.xpath("//a[contains(text(), 'Further Information')]/@href").get()
            or response.xpath("//li[@id='tab_details']//a/@href").get()
        )

        if further_info_url:
            yield scrapy.Request(
                url=response.urljoin(further_info_url),
                callback=self.parse_further_info,
                cb_kwargs={
                    "app_data": app_data,
                    "council_name": council_name,
                    "base_url": base_url,
                },
                meta={"council_name": council_name},
            )
        else:
            # Try to go directly to documents tab
            docs_url = (
                response.xpath("//a[@id='subtab_documents']/@href").get()
                or response.xpath("//a[contains(@href, 'activeTab=documents')]/@href").get()
                or response.xpath("//a[contains(text(), 'Documents')]/@href").get()
                or response.xpath("//li[@id='tab_documents']//a/@href").get()
            )
            if docs_url:
                yield scrapy.Request(
                    url=response.urljoin(docs_url),
                    callback=self.parse_documents_tab,
                    cb_kwargs={
                        "app_data": app_data,
                        "council_name": council_name,
                    },
                    meta={"council_name": council_name},
                )
            else:
                self.logger.warning(
                    f"No further info or documents tab for {app_data.get('application_reference')}"
                )
                # Yield application without documents
                yield self._create_application_item(app_data)

    def parse_further_info(
        self, response, app_data: Dict[str, Any], council_name: str, base_url: str
    ):
        """Parse the Further Information tab to get application type."""
        field_mapping = {
            "Application Type": "application_type",
            "Decision": "decision",
            "Actual Decision Level": "determination_level",
            "Case Officer": "case_officer_name",
            "Parish": "parish",
            "Community": "parish",
            "Ward": "ward",
            "Applicant Name": "applicant_name",
            "Applicant Address": "applicant_address",
            "Agent Name": "agent_name",
            "Agent Company Name": "agent_company_name",
            "Agent Address": "agent_address",
        }

        for row in response.xpath("//table[@id='applicationDetails']//tr"):
            field_name = row.xpath("normalize-space(.//th/text())").get("")
            field_value = row.xpath("normalize-space(.//td/text())").get("")

            if field_name and field_value and field_value != "Not Available":
                if field_name in field_mapping:
                    app_data[field_mapping[field_name]] = field_value

        # Now go to Documents tab - try multiple selectors
        docs_url = (
            response.xpath("//a[@id='subtab_documents']/@href").get()
            or response.xpath("//a[contains(@href, 'activeTab=documents')]/@href").get()
            or response.xpath("//a[contains(text(), 'Documents')]/@href").get()
            or response.xpath("//li[@id='tab_documents']//a/@href").get()
        )

        if docs_url:
            self.logger.debug(f"Found documents tab: {docs_url}")
            yield scrapy.Request(
                url=response.urljoin(docs_url),
                callback=self.parse_documents_tab,
                cb_kwargs={
                    "app_data": app_data,
                    "council_name": council_name,
                },
                meta={"council_name": council_name},
            )
        else:
            # Log that we couldn't find documents tab
            self.logger.warning(
                f"No documents tab found for {app_data.get('application_reference')} - "
                f"URL: {response.url}"
            )
            # Yield application without documents
            yield self._create_application_item(app_data)

    def parse_documents_tab(
        self, response, app_data: Dict[str, Any], council_name: str
    ):
        """
        Parse the Documents tab to extract PDF links.

        IDOX document structure varies but typically has:
        - Table with document rows
        - Each row has: Document Name, Date, Type, Action (download link)
        """
        # First yield the application item
        yield self._create_application_item(app_data)

        app_ref = app_data.get("application_reference", "unknown")
        self.logger.debug(f"Parsing documents tab for {app_ref}: {response.url}")

        # Try multiple table structures used by different IDOX versions
        doc_rows = (
            response.xpath("//table[contains(@class, 'display')]//tbody//tr")
            or response.xpath("//table[@id='documents']//tbody//tr")
            or response.xpath("//table[@id='documents']//tr[position()>1]")
            or response.xpath("//div[@id='Documents']//table//tr[position()>1]")
            or response.xpath("//table[contains(@class, 'documents')]//tr[position()>1]")
            or response.xpath("//div[@class='tabcontainer']//table//tr[td]")
        )

        if not doc_rows:
            # Try alternative structure - some IDOX sites use divs
            doc_rows = response.xpath(
                "//div[@class='documentGroup']//div[contains(@class, 'document')]"
            )

        self.logger.debug(f"Found {len(doc_rows)} document rows for {app_ref}")

        documents_found = 0

        for row in doc_rows:
            doc_item = self._extract_document_from_row(row, app_data, response)
            if doc_item:
                documents_found += 1
                self.stats["documents_found"] += 1
                yield doc_item

        # Check for alternate document formats - direct PDF links anywhere on page
        if documents_found == 0:
            # Look for any PDF-like links
            pdf_links = response.xpath(
                "//a[contains(@href, '.pdf')]/@href"
            ).getall()

            # Also look for ViewDocument links (common IDOX pattern)
            view_doc_links = response.xpath(
                "//a[contains(@href, 'ViewDocument') or contains(@href, 'viewDocument')]/@href"
            ).getall()

            all_doc_links = list(set(pdf_links + view_doc_links))

            self.logger.debug(f"Fallback: found {len(all_doc_links)} direct doc links for {app_ref}")

            for pdf_url in all_doc_links:
                # Get the link text for filename
                link_elem = response.xpath(f"//a[@href='{pdf_url}']")
                if not link_elem:
                    link_elem = response.xpath(f"//a[contains(@href, '{pdf_url}')]")

                link_text = ""
                if link_elem:
                    link_text = link_elem.xpath("string(.)").get("").strip()

                doc_item = DocumentItem(
                    application_reference=app_data.get("application_reference"),
                    council_name=app_data.get("council_name"),
                    document_url=response.urljoin(pdf_url),
                    filename=link_text or self._extract_filename_from_url(pdf_url),
                    source_url=response.url,
                )
                documents_found += 1
                self.stats["documents_found"] += 1
                yield doc_item

        if documents_found > 0:
            self.logger.info(f"Found {documents_found} documents for {app_ref}")
        else:
            self.logger.debug(f"No documents found for {app_ref} at {response.url}")

    def _extract_document_from_row(
        self, row, app_data: Dict[str, Any], response
    ) -> Optional[DocumentItem]:
        """Extract document information from a table row."""
        # Try various selectors for document URL
        doc_url = (
            row.xpath(".//a[contains(@href, '.pdf')]/@href").get()
            or row.xpath(".//a[contains(@href, 'ViewDocument')]/@href").get()
            or row.xpath(".//a[contains(@href, 'download')]/@href").get()
            or row.xpath(".//a/@href").get()
        )

        if not doc_url:
            return None

        # Get document name/filename
        doc_name = (
            row.xpath(".//a/text()").get("")
            or row.xpath(".//td[1]/text()").get("")
            or row.xpath(".//span[@class='description']/text()").get("")
        )
        doc_name = doc_name.strip() if doc_name else ""

        if not doc_name:
            doc_name = self._extract_filename_from_url(doc_url)

        # Skip non-PDF documents if URL doesn't look like a PDF
        if not self._is_likely_pdf(doc_url, doc_name):
            return None

        return DocumentItem(
            application_reference=app_data.get("application_reference"),
            council_name=app_data.get("council_name"),
            document_url=response.urljoin(doc_url),
            filename=doc_name,
            source_url=response.url,
        )

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

        # Default to true for unknown types (server will return PDF or not)
        return True

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        # Handle various URL patterns
        if "/" in url:
            filename = url.split("/")[-1]
            # Remove query string
            if "?" in filename:
                filename = filename.split("?")[0]
            return filename
        return "document.pdf"

    def _create_application_item(
        self, app_data: Dict[str, Any]
    ) -> PlanningApplicationItem:
        """Create a PlanningApplicationItem from parsed data."""
        item = PlanningApplicationItem()

        for key, value in app_data.items():
            if value and key in item.fields:
                item[key] = value

        item["_portal_framework"] = "idox"
        item["_scraped_at"] = datetime.utcnow().isoformat()

        return item
