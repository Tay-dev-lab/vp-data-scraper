"""
Application Filter Pipeline - filters to residential/householder applications only.

This pipeline runs FIRST (priority 50) to avoid processing non-residential applications.
"""

import logging
from scrapy.exceptions import DropItem

from ..items.application import PlanningApplicationItem
from ..services.application_filter import ResidentialApplicationFilter


class ApplicationFilterPipeline:
    """
    Filter pipeline that keeps only residential/householder applications.

    Target application types:
    - Extensions and alterations
    - Refurbishments
    - Loft conversions
    - Small new builds (up to 10 houses or 20 apartments)

    Non-matching applications are dropped before any PDF downloads occur.
    """

    def __init__(self):
        self.filter = ResidentialApplicationFilter()
        self.logger = logging.getLogger(__name__)
        self.stats = {
            "total_applications": 0,
            "accepted": 0,
            "rejected": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler."""
        return cls()

    def process_item(self, item, spider):
        """
        Process an item through the residential filter.

        Only PlanningApplicationItems are filtered - DocumentItems pass through.
        """
        # Only filter PlanningApplicationItems
        if not isinstance(item, PlanningApplicationItem):
            return item

        self.stats["total_applications"] += 1

        application_type = item.get("application_type", "")
        proposal = item.get("proposal", "")

        if self.filter.is_residential(application_type, proposal):
            self.stats["accepted"] += 1
            self.logger.debug(
                f"Accepted residential application: {item.get('application_reference')}"
            )
            return item

        # Get rejection reason for logging
        reason = self.filter.get_rejection_reason(application_type, proposal)
        self.stats["rejected"] += 1

        self.logger.debug(
            f"Rejected non-residential application: {item.get('application_reference')} - {reason}"
        )

        raise DropItem(
            f"Non-residential application dropped: {item.get('application_reference')}"
        )

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"Application filter stats: {self.stats['total_applications']} total, "
            f"{self.stats['accepted']} accepted, {self.stats['rejected']} rejected"
        )
        spider.crawler.stats.set_value(
            "application_filter/total", self.stats["total_applications"]
        )
        spider.crawler.stats.set_value(
            "application_filter/accepted", self.stats["accepted"]
        )
        spider.crawler.stats.set_value(
            "application_filter/rejected", self.stats["rejected"]
        )
