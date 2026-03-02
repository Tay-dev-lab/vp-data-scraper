"""
Application State Tracker for coordinating async pipeline processing.

This module provides a centralized state management system that coordinates
async operations (like LLM classification) using Twisted Deferreds. It
solves race conditions where documents may arrive before their parent
application's async classification completes.
"""

import logging
from typing import Optional

from twisted.internet.defer import Deferred

logger = logging.getLogger(__name__)


class ApplicationStateTracker:
    """
    Tracks classification state of applications across pipelines.

    States:
        CLASSIFYING: Application is being processed by async LLM filter
        QUALIFIED: Application passed LLM filter
        REJECTED: Application was rejected by any filter

    Usage:
        # In LLM filter (BEFORE async call):
        state_tracker.mark_classifying(key)

        # In LLM filter callback:
        state_tracker.mark_qualified(key)  # or mark_rejected(key)

        # In document filter:
        if state_tracker.is_rejected(key):
            raise DropItem(...)
        if state_tracker.is_classifying(key):
            d = state_tracker.wait_for_classification(key)
            d.addCallback(lambda qualified: process_if_qualified(qualified))
            return d
    """

    def __init__(self):
        # key -> Deferred (fires when classification completes)
        self._classifying: dict[str, Deferred] = {}

        # Keys that passed LLM filter
        self._qualified: set[str] = set()

        # Keys rejected by any filter (LLM or sync filters)
        self._rejected: set[str] = set()

        # Track waiters for diagnostic purposes
        self._waiter_count: dict[str, int] = {}

    def mark_classifying(self, key: str) -> None:
        """
        Mark application as being classified (BEFORE async call).

        This MUST be called synchronously before starting async classification
        to prevent race conditions where documents arrive during classification.

        Args:
            key: Application key in format "council:reference"
        """
        if key not in self._classifying:
            self._classifying[key] = Deferred()
            self._waiter_count[key] = 0
            logger.debug(f"Application marked as classifying: {key}")

    def mark_qualified(self, key: str) -> None:
        """
        Mark application as qualified (passed LLM filter).

        Args:
            key: Application key in format "council:reference"
        """
        self._qualified.add(key)
        self._resolve_waiters(key, qualified=True)
        logger.debug(f"Application marked as qualified: {key}")

    def mark_rejected(self, key: str) -> None:
        """
        Mark application as rejected by any filter.

        Args:
            key: Application key in format "council:reference"
        """
        self._rejected.add(key)
        self._resolve_waiters(key, qualified=False)
        logger.debug(f"Application marked as rejected: {key}")

    def _resolve_waiters(self, key: str, qualified: bool) -> None:
        """
        Resolve Deferreds waiting for this classification.

        Args:
            key: Application key in format "council:reference"
            qualified: True if qualified, False if rejected
        """
        if key in self._classifying:
            d = self._classifying.pop(key)
            waiter_count = self._waiter_count.pop(key, 0)

            if not d.called:
                d.callback(qualified)

            if waiter_count > 0:
                logger.debug(
                    f"Resolved {waiter_count} waiting document(s) for {key} "
                    f"(qualified={qualified})"
                )

    def is_rejected(self, key: str) -> bool:
        """Check if application has been rejected."""
        return key in self._rejected

    def is_qualified(self, key: str) -> bool:
        """Check if application has been qualified."""
        return key in self._qualified

    def is_classifying(self, key: str) -> bool:
        """Check if application is currently being classified."""
        return key in self._classifying

    def get_state(self, key: str) -> str:
        """
        Get current state of an application.

        Returns:
            One of: "classifying", "qualified", "rejected", "unknown"
        """
        if key in self._classifying:
            return "classifying"
        if key in self._qualified:
            return "qualified"
        if key in self._rejected:
            return "rejected"
        return "unknown"

    def wait_for_classification(self, key: str) -> Deferred:
        """
        Return Deferred that fires when classification completes.

        The Deferred callbacks with True (qualified) or False (rejected).

        Args:
            key: Application key in format "council:reference"

        Returns:
            Deferred that fires with qualification result
        """
        # Already qualified
        if key in self._qualified:
            d = Deferred()
            d.callback(True)
            return d

        # Already rejected
        if key in self._rejected:
            d = Deferred()
            d.callback(False)
            return d

        # Currently classifying - create chained Deferred
        if key in self._classifying:
            original = self._classifying[key]

            # Track waiter count for diagnostics
            self._waiter_count[key] = self._waiter_count.get(key, 0) + 1

            # Create new Deferred chained to original
            clone = Deferred()

            def forward_result(result):
                if not clone.called:
                    clone.callback(result)
                return result

            def forward_error(failure):
                if not clone.called:
                    clone.errback(failure)
                return failure

            original.addCallback(forward_result)
            original.addErrback(forward_error)

            logger.debug(
                f"Document waiting for classification of {key} "
                f"(waiter #{self._waiter_count[key]})"
            )
            return clone

        # Not tracked - assume qualified (for applications that skipped LLM filter)
        d = Deferred()
        d.callback(True)
        return d

    def get_stats(self) -> dict:
        """Get statistics about tracked applications."""
        return {
            "classifying": len(self._classifying),
            "qualified": len(self._qualified),
            "rejected": len(self._rejected),
        }
