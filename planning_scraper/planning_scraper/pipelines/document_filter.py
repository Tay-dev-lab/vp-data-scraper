"""
Document Filter Pipeline - filters to planning drawings only.

This pipeline runs after ApplicationFilterPipeline (priority 100).
Only PDFs matching drawing patterns are kept for download.
"""

import logging
from scrapy.exceptions import DropItem

from ..items.document import DocumentItem
from ..services.pdf_filter import DrawingPatternMatcher


class DocumentFilterPipeline:
    """
    Filter pipeline that keeps only planning drawing documents.

    Target document types:
    - Site plans
    - Floor plans
    - Elevations
    - Block plans
    - Location plans
    - Sections

    Excludes:
    - Application forms
    - Statements
    - Reports
    - Letters
    - Decision notices
    """

    def __init__(self):
        self.matcher = DrawingPatternMatcher()
        self.logger = logging.getLogger(__name__)
        self.stats = {
            "total_documents": 0,
            "accepted": 0,
            "rejected": 0,
            "skipped_no_parent": 0,
            "by_type": {},
        }
        # Track approved applications (populated by LLM filter)
        self._approved_apps = set()

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        pipeline = cls()
        pipeline.crawler = crawler
        return pipeline

    def process_item(self, item, spider):
        """
        Process a document through the drawing filter.

        Only DocumentItems are filtered - PlanningApplicationItems pass through.
        """
        # Only filter DocumentItems
        if not isinstance(item, DocumentItem):
            # Track approved applications from LLM filter
            if item.get("_llm_approved"):
                council = item.get("council_name", "")
                ref = item.get("application_reference", "")
                key = f"{council}:{ref}"
                self._approved_apps.add(key)
            return item

        self.stats["total_documents"] += 1

        # Check if parent application was approved
        council = item.get("council_name", "")
        ref = item.get("application_reference", "")
        key = f"{council}:{ref}"

        if key not in self._approved_apps:
            self.stats["skipped_no_parent"] += 1
            self.logger.debug(
                f"Skipping document {item.get('filename')} - parent application {key} not approved"
            )
            raise DropItem(f"Document skipped - parent application {ref} was not approved")

        filename = item.get("filename", "")
        match = self.matcher.match(filename)

        if match.is_drawing:
            self.stats["accepted"] += 1

            # Track by document type
            doc_type = match.document_type or "unknown"
            self.stats["by_type"][doc_type] = self.stats["by_type"].get(doc_type, 0) + 1

            # Set document type and match info on item
            item["document_type"] = doc_type
            item["matches_pattern"] = True
            item["matched_patterns"] = [match.matched_pattern] if match.matched_pattern else []

            self.logger.debug(
                f"Accepted drawing: {filename} (type: {doc_type}, "
                f"pattern: {match.matched_pattern})"
            )
            return item

        # Document didn't match drawing patterns
        self.stats["rejected"] += 1

        self.logger.debug(
            f"Rejected non-drawing document: {filename} "
            f"(app: {item.get('application_reference')})"
        )

        raise DropItem(f"Non-drawing document dropped: {filename}")

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"Document filter stats: {self.stats['total_documents']} total, "
            f"{self.stats['accepted']} accepted, {self.stats['rejected']} rejected, "
            f"{self.stats['skipped_no_parent']} skipped (no approved parent)"
        )
        self.logger.info(f"Documents by type: {self.stats['by_type']}")

        spider.crawler.stats.set_value(
            "document_filter/total", self.stats["total_documents"]
        )
        spider.crawler.stats.set_value(
            "document_filter/accepted", self.stats["accepted"]
        )
        spider.crawler.stats.set_value(
            "document_filter/rejected", self.stats["rejected"]
        )
        spider.crawler.stats.set_value(
            "document_filter/skipped_no_parent", self.stats["skipped_no_parent"]
        )
        for doc_type, count in self.stats["by_type"].items():
            spider.crawler.stats.set_value(
                f"document_filter/type/{doc_type}", count
            )
