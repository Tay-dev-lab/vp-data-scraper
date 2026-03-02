"""
Document Filter Pipeline - filters to planning drawings only.

This pipeline runs after ApplicationFilterPipeline (priority 100).
Only PDFs matching drawing patterns are kept for download.

IMPORTANT: This pipeline coordinates with the LLM filter to handle race
conditions. If a document's parent application is still being classified
by the async LLM filter, this pipeline will wait for classification to
complete before processing the document.
"""

import logging
from scrapy.exceptions import DropItem
from twisted.internet.defer import Deferred

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
            "skipped_parent_rejected": 0,
            "waited_for_classification": 0,
            "by_type": {},
        }

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

        If parent application is still being classified by LLM filter, this
        will wait for classification to complete before processing.
        """
        # Only filter DocumentItems
        if not isinstance(item, DocumentItem):
            return item

        self.stats["total_documents"] += 1

        # Check if parent application was rejected (via spider's shared set)
        council = item.get("council_name", "")
        ref = item.get("application_reference", "")
        key = f"{council}:{ref}"

        # Check application state tracker for async classification status
        app_state = getattr(spider, "_app_state", None)

        if app_state:
            # Check if already rejected (fast path)
            if app_state.is_rejected(key):
                self.stats["skipped_parent_rejected"] += 1
                self.logger.debug(
                    f"Skipping document {item.get('filename')} - "
                    f"parent application {key} was rejected (state tracker)"
                )
                raise DropItem(f"Document skipped - parent application {ref} was rejected")

            # Check if classification is in progress (need to wait)
            if app_state.is_classifying(key):
                self.stats["waited_for_classification"] += 1
                self.logger.debug(
                    f"Document {item.get('filename')} waiting for parent "
                    f"application {key} classification to complete"
                )
                # Return Deferred that fires when classification completes
                return self._wait_and_process(item, spider, key, app_state)

        # Also check legacy rejected_apps set for backwards compatibility
        rejected_apps = getattr(spider, "_rejected_applications", set())
        if key in rejected_apps:
            self.stats["skipped_parent_rejected"] += 1
            self.logger.debug(
                f"Skipping document {item.get('filename')} - parent application {key} was rejected"
            )
            raise DropItem(f"Document skipped - parent application {ref} was rejected")

        # Process document through drawing filter
        return self._filter_document(item)

    def _wait_and_process(self, item, spider, key, app_state):
        """
        Wait for parent application classification to complete, then process.

        Returns a Deferred that fires with the processed item or raises DropItem.
        """
        d = app_state.wait_for_classification(key)

        def on_classification_complete(qualified):
            if not qualified:
                self.stats["skipped_parent_rejected"] += 1
                self.logger.debug(
                    f"Document {item.get('filename')} dropped after waiting - "
                    f"parent application {key} was rejected"
                )
                raise DropItem(
                    f"Document skipped - parent application {item.get('application_reference')} was rejected"
                )
            # Parent qualified, process document through drawing filter
            return self._filter_document(item)

        def on_error(failure):
            # If it's a DropItem (from on_classification_complete or _filter_document),
            # just re-raise it - this is expected behavior, not an error
            if failure.check(DropItem):
                return failure

            # On actual error, log and drop the document to be safe
            self.logger.error(
                f"Error waiting for classification of {key}: {failure.value}"
            )
            raise DropItem(
                f"Document skipped - error waiting for parent classification: {failure.value}"
            )

        d.addCallback(on_classification_complete)
        d.addErrback(on_error)
        return d

    def _filter_document(self, item):
        """Apply drawing pattern matching to filter document."""
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
            f"{self.stats['skipped_parent_rejected']} skipped (parent rejected), "
            f"{self.stats['waited_for_classification']} waited for classification"
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
            "document_filter/skipped_parent_rejected", self.stats["skipped_parent_rejected"]
        )
        spider.crawler.stats.set_value(
            "document_filter/waited_for_classification", self.stats["waited_for_classification"]
        )
        for doc_type, count in self.stats["by_type"].items():
            spider.crawler.stats.set_value(
                f"document_filter/type/{doc_type}", count
            )
