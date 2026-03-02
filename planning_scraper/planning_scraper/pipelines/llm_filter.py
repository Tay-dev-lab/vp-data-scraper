"""
LLM Application Filter Pipeline - uses LLM to classify applications.

This pipeline runs after the regex-based filters (priority 75) to provide
intelligent classification of applications as new build or conversion.

IMPORTANT: This pipeline uses async LLM calls via Twisted deferToThread.
To prevent race conditions with document processing, it marks applications
as CLASSIFYING before starting the async call, then marks them QUALIFIED
or REJECTED in the callback. Documents wait for classification if needed.
"""

import logging
import asyncio
from typing import Optional

from scrapy.exceptions import DropItem
from twisted.internet import threads

from ..items.application import PlanningApplicationItem
from ..services.llm import get_llm_provider, PlanningApplicationClassifier, LLMCache
from ..services.llm.base import LLMError
from ..utils.state_tracker import ApplicationStateTracker


class LLMApplicationFilterPipeline:
    """
    Pipeline that uses an LLM to classify planning applications.

    Filters applications to keep only:
    - NEW BUILD residential (1-30 units)
    - CONVERSION to residential (1-30 units)

    Uses async LLM calls with caching to minimize API costs.
    """

    def __init__(
        self,
        enabled: bool = True,
        provider_name: str = "openai",
        fallback_mode: str = "permissive",
        cache_ttl: int = 86400,
        min_units: int = 1,
        max_units: int = 30,
        settings: Optional[dict] = None,
    ):
        """
        Initialize the LLM filter pipeline.

        Args:
            enabled: Whether the filter is active
            provider_name: LLM provider to use ('openai', 'anthropic', 'ollama')
            fallback_mode: Behavior on error - 'permissive' (pass) or 'strict' (drop)
            cache_ttl: Cache time-to-live in seconds (default: 24 hours)
            min_units: Minimum units to qualify (default: 1)
            max_units: Maximum units to qualify (default: 30)
            settings: Scrapy settings dictionary
        """
        self.enabled = enabled
        self.provider_name = provider_name
        self.fallback_mode = fallback_mode
        self.cache_ttl = cache_ttl
        self.min_units = min_units
        self.max_units = max_units
        self.settings = settings or {}

        self.logger = logging.getLogger(__name__)
        self.classifier: Optional[PlanningApplicationClassifier] = None
        self._initialized = False
        self._spider = None  # Set during open_spider

        # Statistics
        self.stats = {
            "total": 0,
            "qualified": 0,
            "not_qualified": 0,
            "new_build": 0,
            "conversion": 0,
            "extension": 0,
            "other": 0,
            "errors": 0,
            "fallback_passed": 0,
        }

    @classmethod
    def from_crawler(cls, crawler):
        """Create pipeline instance from crawler settings."""
        settings = crawler.settings

        enabled = settings.getbool("LLM_FILTER_ENABLED", True)
        provider_name = settings.get("LLM_PROVIDER", "openai")
        fallback_mode = settings.get("LLM_FILTER_FALLBACK", "permissive")
        cache_ttl = settings.getint("LLM_FILTER_CACHE_TTL", 86400)
        min_units = settings.getint("LLM_FILTER_MIN_UNITS", 1)
        max_units = settings.getint("LLM_FILTER_MAX_UNITS", 30)

        # Convert settings to dict for provider initialization
        settings_dict = {
            "LLM_API_KEY": settings.get("LLM_API_KEY"),
            "LLM_MODEL": settings.get("LLM_MODEL"),
            "OPENAI_API_KEY": settings.get("OPENAI_API_KEY"),
            "ANTHROPIC_API_KEY": settings.get("ANTHROPIC_API_KEY"),
            "OLLAMA_BASE_URL": settings.get("OLLAMA_BASE_URL"),
        }

        return cls(
            enabled=enabled,
            provider_name=provider_name,
            fallback_mode=fallback_mode,
            cache_ttl=cache_ttl,
            min_units=min_units,
            max_units=max_units,
            settings=settings_dict,
        )

    def open_spider(self, spider):
        """Store spider reference and initialize state tracker."""
        self._spider = spider

        # Initialize the rejected applications set (legacy, for backwards compatibility)
        if not hasattr(spider, "_rejected_applications"):
            spider._rejected_applications = set()

        # Initialize the application state tracker (shared across pipelines)
        if not hasattr(spider, "_app_state"):
            spider._app_state = ApplicationStateTracker()
            self.logger.debug("Initialized ApplicationStateTracker on spider")

    def _mark_application_rejected(self, item):
        """Mark an application as rejected so its documents will be dropped."""
        council = item.get("council_name", "")
        ref = item.get("application_reference", "")
        key = f"{council}:{ref}"

        # Store in a set on the spider, accessible to all pipelines
        if self._spider:
            if not hasattr(self._spider, "_rejected_applications"):
                self._spider._rejected_applications = set()
            self._spider._rejected_applications.add(key)

    def _initialize_classifier(self):
        """Initialize the LLM classifier (lazy initialization)."""
        if self._initialized:
            return

        try:
            provider = get_llm_provider(self.provider_name, self.settings)
            cache = LLMCache(ttl_seconds=self.cache_ttl)
            self.classifier = PlanningApplicationClassifier(
                provider=provider,
                cache=cache,
                min_units=self.min_units,
                max_units=self.max_units,
            )
            self._initialized = True
            self.logger.info(
                f"LLM classifier initialized with provider: {self.provider_name}"
            )
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM classifier: {e}")
            raise

    def _run_classification_sync(self, proposal: str, application_type: str, address: str):
        """
        Run the async classification in a new event loop (for thread pool).

        This runs in a separate thread via Twisted's deferToThread,
        so it's safe to create a new event loop here.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.classifier.classify(
                    proposal=proposal,
                    application_type=application_type,
                    address=address,
                )
            )
        finally:
            loop.close()

    def process_item(self, item, spider):
        """
        Process an item through the LLM classifier.

        Uses Twisted's deferToThread to run async LLM calls
        without blocking the reactor.
        """
        # Only filter PlanningApplicationItems
        if not isinstance(item, PlanningApplicationItem):
            return item

        # Skip if filter is disabled - passes through without rejection
        if not self.enabled:
            return item

        self.stats["total"] += 1

        # Lazy initialization
        if not self._initialized:
            try:
                self._initialize_classifier()
            except Exception as e:
                self.logger.error(f"Failed to initialize classifier: {e}")
                if self.fallback_mode == "permissive":
                    self.stats["fallback_passed"] += 1
                    return item
                raise DropItem(f"LLM classifier initialization failed: {e}")

        # Get proposal text
        proposal = item.get("proposal", "")
        application_type = item.get("application_type", "")
        address = item.get("site_address", "")

        if not proposal:
            self.logger.debug(
                f"No proposal text for {item.get('application_reference')}"
            )
            if self.fallback_mode == "permissive":
                self.stats["fallback_passed"] += 1
                return item
            raise DropItem(
                f"Application {item.get('application_reference')} has no proposal text"
            )

        # Generate key for state tracking
        council = item.get("council_name", "")
        ref = item.get("application_reference", "")
        key = f"{council}:{ref}"

        # CRITICAL: Mark as classifying BEFORE starting async to prevent race condition
        # Documents arriving while classification is in progress will wait for result
        if hasattr(self._spider, "_app_state"):
            self._spider._app_state.mark_classifying(key)
            self.logger.debug(f"Marked application {key} as classifying before async call")

        # Use deferToThread to run the async code in a thread pool
        d = threads.deferToThread(
            self._run_classification_sync,
            proposal,
            application_type,
            address,
        )

        # Add callback to process the result (pass key for state tracking)
        d.addCallback(self._handle_classification_result, item, key)
        d.addErrback(self._handle_classification_error, item, key)

        return d

    def _handle_classification_result(self, result, item, key):
        """Handle successful classification result."""
        # Store classification result on item
        item["_llm_classification"] = result.to_dict()

        # Update statistics by development type
        dev_type = result.development_type
        if dev_type in self.stats:
            self.stats[dev_type] += 1

        if result.qualifies:
            self.stats["qualified"] += 1
            self.logger.info(
                f"LLM QUALIFIED: {item.get('application_reference')} - "
                f"{result.development_type} ({result.unit_count} units) - "
                f"{result.reason}"
            )
            # Mark as qualified in state tracker (resolves waiting documents)
            if self._spider and hasattr(self._spider, "_app_state"):
                self._spider._app_state.mark_qualified(key)
            return item
        else:
            self.stats["not_qualified"] += 1
            self.logger.info(
                f"LLM NOT QUALIFIED: {item.get('application_reference')} - "
                f"{result.development_type} - {result.reason}"
            )
            # Mark as rejected in state tracker FIRST (resolves waiting documents)
            if self._spider and hasattr(self._spider, "_app_state"):
                self._spider._app_state.mark_rejected(key)
            # Also mark in legacy set for backwards compatibility
            self._mark_application_rejected(item)
            raise DropItem(
                f"Application {item.get('application_reference')} not qualified: "
                f"{result.reason}"
            )

    def _handle_classification_error(self, failure, item, key):
        """Handle classification error."""
        # Extract the actual exception
        error = failure.value

        # If this is a DropItem from _handle_classification_result (intentional rejection),
        # re-raise it - don't treat it as an error (state already tracked in result handler)
        if isinstance(error, DropItem):
            return failure

        # This is an actual error (API failure, timeout, etc.)
        self.stats["errors"] += 1

        self.logger.error(
            f"LLM error for {item.get('application_reference')}: {error}"
        )

        if self.fallback_mode == "permissive":
            self.stats["fallback_passed"] += 1
            self.logger.warning(
                f"Passing application {item.get('application_reference')} "
                f"due to LLM error (permissive mode)"
            )
            # Mark as qualified in state tracker (allowing documents through)
            if self._spider and hasattr(self._spider, "_app_state"):
                self._spider._app_state.mark_qualified(key)
            return item
        else:
            # Mark as rejected in state tracker
            if self._spider and hasattr(self._spider, "_app_state"):
                self._spider._app_state.mark_rejected(key)
            self._mark_application_rejected(item)
            raise DropItem(
                f"Application {item.get('application_reference')} dropped due to LLM error: {error}"
            )

    def close_spider(self, spider):
        """Log statistics when spider closes."""
        self.logger.info(
            f"LLM filter stats: {self.stats['total']} total, "
            f"{self.stats['qualified']} qualified, "
            f"{self.stats['not_qualified']} not qualified, "
            f"{self.stats['errors']} errors"
        )
        self.logger.info(
            f"LLM filter breakdown: "
            f"{self.stats['new_build']} new build, "
            f"{self.stats['conversion']} conversion, "
            f"{self.stats['extension']} extension, "
            f"{self.stats['other']} other"
        )

        if self.classifier:
            cache_stats = self.classifier.get_cache_stats()
            self.logger.info(
                f"LLM cache stats: {cache_stats['hits']} hits, "
                f"{cache_stats['misses']} misses, "
                f"{cache_stats['hit_rate_percent']}% hit rate"
            )

        # Set stats in crawler
        for key, value in self.stats.items():
            spider.crawler.stats.set_value(f"llm_filter/{key}", value)

        if self.classifier:
            cache_stats = self.classifier.get_cache_stats()
            spider.crawler.stats.set_value("llm_filter/cache_hits", cache_stats["hits"])
            spider.crawler.stats.set_value("llm_filter/cache_misses", cache_stats["misses"])
            spider.crawler.stats.set_value(
                "llm_filter/cache_hit_rate", cache_stats["hit_rate_percent"]
            )

        # Log state tracker stats
        if hasattr(spider, "_app_state"):
            state_stats = spider._app_state.get_stats()
            self.logger.info(
                f"State tracker stats: {state_stats['qualified']} qualified, "
                f"{state_stats['rejected']} rejected, "
                f"{state_stats['classifying']} still classifying"
            )
            spider.crawler.stats.set_value(
                "state_tracker/qualified", state_stats["qualified"]
            )
            spider.crawler.stats.set_value(
                "state_tracker/rejected", state_stats["rejected"]
            )
