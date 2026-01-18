"""
Approval Status Filter Pipeline - filters to approved applications only.

This pipeline runs FIRST (priority 40) to avoid processing applications
that haven't been approved.
"""

import re
import logging
from scrapy.exceptions import DropItem

from ..items.application import PlanningApplicationItem


class ApprovalStatusFilterPipeline:
    """
    Filter pipeline that keeps only approved applications.

    This is a simple regex-based filter that checks the 'decision' field
    for approval patterns. It runs before all other filters to eliminate
    applications early in the pipeline.

    Uses lenient mode: applications with empty/null decision fields pass through
    to avoid false negatives when data is missing.
    """

    # Patterns that indicate an approved application
    APPROVAL_PATTERNS = [
        r"\bapproved\b",
        r"\bgranted\b",
        r"\bpermission\s+granted\b",
        r"\bapproval\b",
        r"\bpermit\s+issued\b",
        r"\bauthorised\b",
        r"\bauthorized\b",
        r"\bapplication\s+permitted\b",
        r"\bdecision:\s*grant\b",
    ]

    # Patterns that explicitly indicate rejection (used for stats only)
    REJECTION_PATTERNS = [
        r"\brefused\b",
        r"\brejected\b",
        r"\bdenied\b",
        r"\bwithdrawn\b",
        r"\bdismissed\b",
        r"\bdeclined\b",
    ]

    def __init__(self, enabled: bool = True, lenient_mode: bool = True):
        """
        Initialize the filter.

        Args:
            enabled: Whether the filter is active (default: True)
            lenient_mode: If True, pass items with empty decision field (default: True)
        """
        self.enabled = enabled
        self.lenient_mode = lenient_mode
        self.logger = logging.getLogger(__name__)

        # Pre-compile patterns
        self._approval_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.APPROVAL_PATTERNS
        ]
        self._rejection_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.REJECTION_PATTERNS
        ]

        # Statistics
        self.stats = {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "no_decision": 0,
            "other_status": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler settings."""
        enabled = crawler.settings.getbool("APPROVAL_FILTER_ENABLED", True)
        lenient_mode = crawler.settings.getbool("APPROVAL_FILTER_LENIENT", True)
        return cls(enabled=enabled, lenient_mode=lenient_mode)

    def process_item(self, item, spider):
        """
        Process an item through the approval filter.

        Only PlanningApplicationItems are filtered - DocumentItems pass through.
        """
        # Only filter PlanningApplicationItems
        if not isinstance(item, PlanningApplicationItem):
            return item

        # Skip if filter is disabled
        if not self.enabled:
            return item

        self.stats["total"] += 1

        decision = (item.get("decision") or "").strip().lower()

        # Handle empty decision field
        if not decision:
            self.stats["no_decision"] += 1
            if self.lenient_mode:
                self.logger.debug(
                    f"No decision field for {item.get('application_reference')}, "
                    f"passing through (lenient mode)"
                )
                return item
            else:
                raise DropItem(
                    f"Application {item.get('application_reference')} has no decision"
                )

        # Check for approval patterns
        for pattern in self._approval_patterns:
            if pattern.search(decision):
                self.stats["approved"] += 1
                self.logger.debug(
                    f"Approved application: {item.get('application_reference')} - {decision}"
                )
                return item

        # Check for explicit rejection (for statistics)
        for pattern in self._rejection_patterns:
            if pattern.search(decision):
                self.stats["rejected"] += 1
                self.logger.debug(
                    f"Rejected (refused) application: {item.get('application_reference')} - {decision}"
                )
                raise DropItem(
                    f"Application {item.get('application_reference')} was refused: {decision}"
                )

        # Other status (pending, under review, etc.)
        self.stats["other_status"] += 1
        self.logger.debug(
            f"Non-approved status for {item.get('application_reference')}: {decision}"
        )
        raise DropItem(
            f"Application {item.get('application_reference')} not approved: {decision}"
        )

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"Approval filter stats: {self.stats['total']} total, "
            f"{self.stats['approved']} approved, "
            f"{self.stats['rejected']} refused, "
            f"{self.stats['no_decision']} no decision, "
            f"{self.stats['other_status']} other status"
        )

        # Set stats in crawler
        for key, value in self.stats.items():
            spider.crawler.stats.set_value(f"approval_filter/{key}", value)
