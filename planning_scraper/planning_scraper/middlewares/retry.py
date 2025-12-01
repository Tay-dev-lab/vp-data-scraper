"""
Retry Middleware - handles special retry cases.

Includes handling for:
- 202 Accepted (async processing)
- Rate limiting (429)
- Server errors (5xx)
"""

import logging
import time
from typing import Optional

from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.http import Request, Response
from scrapy.utils.response import response_status_message


class Handle202Middleware:
    """
    Middleware that handles HTTP 202 Accepted responses.

    Some planning portals return 202 when processing large searches.
    This middleware waits and retries the request.

    Settings:
    - HANDLE_202_WAIT: Seconds to wait before retry (default: 5)
    - HANDLE_202_MAX_RETRIES: Maximum retry attempts (default: 3)
    """

    def __init__(
        self,
        wait_time: float = 5.0,
        max_retries: int = 3,
    ):
        self.wait_time = wait_time
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        wait_time = crawler.settings.getfloat("HANDLE_202_WAIT", 5.0)
        max_retries = crawler.settings.getint("HANDLE_202_MAX_RETRIES", 3)

        return cls(wait_time=wait_time, max_retries=max_retries)

    def process_response(self, request: Request, response: Response, spider):
        """Handle 202 responses by waiting and retrying."""
        if response.status != 202:
            return response

        retry_count = request.meta.get("handle_202_retry", 0)

        if retry_count >= self.max_retries:
            self.logger.warning(
                f"Max 202 retries reached for {request.url}, proceeding with response"
            )
            return response

        self.logger.info(
            f"Got 202 response for {request.url}, "
            f"waiting {self.wait_time}s before retry ({retry_count + 1}/{self.max_retries})"
        )

        time.sleep(self.wait_time)

        # Create new request with incremented retry count
        new_request = request.copy()
        new_request.meta["handle_202_retry"] = retry_count + 1
        new_request.dont_filter = True

        return new_request


class RateLimitMiddleware:
    """
    Middleware that handles rate limiting (429) responses.

    Features:
    - Exponential backoff
    - Per-domain tracking
    - Respects Retry-After header

    Settings:
    - RATE_LIMIT_INITIAL_WAIT: Initial wait time (default: 30)
    - RATE_LIMIT_MAX_WAIT: Maximum wait time (default: 300)
    - RATE_LIMIT_MAX_RETRIES: Maximum retries (default: 5)
    """

    def __init__(
        self,
        initial_wait: float = 30.0,
        max_wait: float = 300.0,
        max_retries: int = 5,
    ):
        self.initial_wait = initial_wait
        self.max_wait = max_wait
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        return cls(
            initial_wait=crawler.settings.getfloat("RATE_LIMIT_INITIAL_WAIT", 30.0),
            max_wait=crawler.settings.getfloat("RATE_LIMIT_MAX_WAIT", 300.0),
            max_retries=crawler.settings.getint("RATE_LIMIT_MAX_RETRIES", 5),
        )

    def process_response(self, request: Request, response: Response, spider):
        """Handle 429 responses with exponential backoff."""
        if response.status != 429:
            return response

        retry_count = request.meta.get("rate_limit_retry", 0)

        if retry_count >= self.max_retries:
            self.logger.error(
                f"Max rate limit retries reached for {request.url}"
            )
            return response

        # Check for Retry-After header
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                wait_time = float(retry_after.decode() if isinstance(retry_after, bytes) else retry_after)
            except ValueError:
                wait_time = self.initial_wait * (2 ** retry_count)
        else:
            # Exponential backoff
            wait_time = min(
                self.initial_wait * (2 ** retry_count),
                self.max_wait,
            )

        self.logger.warning(
            f"Rate limited on {request.url}, "
            f"waiting {wait_time}s ({retry_count + 1}/{self.max_retries})"
        )

        time.sleep(wait_time)

        new_request = request.copy()
        new_request.meta["rate_limit_retry"] = retry_count + 1
        new_request.dont_filter = True

        return new_request


class CustomRetryMiddleware(RetryMiddleware):
    """
    Extended retry middleware with custom logic.

    Adds:
    - Better logging
    - Per-domain retry tracking
    - Custom status codes
    """

    def __init__(self, settings):
        super().__init__(settings)
        self.logger = logging.getLogger(__name__)

    def process_response(self, request: Request, response: Response, spider):
        """Process response and retry if needed."""
        if request.meta.get("dont_retry", False):
            return response

        # Add custom retry status codes
        custom_retry_codes = {502, 503, 504, 520, 521, 522, 523, 524}

        if response.status in custom_retry_codes:
            reason = response_status_message(response.status)
            self.logger.debug(
                f"Got {response.status} ({reason}) for {request.url}, retrying..."
            )
            return self._retry(request, reason, spider) or response

        return super().process_response(request, response, spider)

    def process_exception(self, request: Request, exception, spider):
        """Process exceptions and retry if appropriate."""
        self.logger.debug(f"Got exception {exception} for {request.url}")
        return super().process_exception(request, exception, spider)
