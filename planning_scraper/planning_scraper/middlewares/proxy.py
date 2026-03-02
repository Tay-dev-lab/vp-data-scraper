"""
Proxy Middleware - adds proxy support for requests.

Uses sticky proxy sessions for consistent IP per spider run.
"""

import logging
import os
import random
import string
from typing import Optional

from scrapy import signals
from scrapy.http import Request


class ProxyMiddleware:
    """
    Middleware that adds proxy support to requests.

    Configuration:
    - PROXY_URL: Full proxy URL (e.g., http://user:pass@proxy.example.com:8080)
    - PROXY_ENABLED: Enable/disable proxy (default: True if PROXY_URL set)

    If PROXY_URL contains '-session-' placeholder, generates unique session ID per run.

    Usage:
        Set PROXY_URL in settings or environment variable.
        The middleware will automatically add the proxy to all requests.
    """

    def __init__(self, proxy_url: Optional[str] = None, enabled: bool = True):
        self.logger = logging.getLogger(__name__)
        self.original_proxy_url = proxy_url
        self.proxy_url = self._generate_session_url(proxy_url)
        self.enabled = enabled and bool(proxy_url)

    def _generate_session_url(self, proxy_url: Optional[str]) -> Optional[str]:
        """Generate unique session ID for sticky proxy if URL contains session placeholder."""
        if not proxy_url:
            return None

        # Generate random session ID for this spider run
        session_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))

        # Replace existing session ID or add new one
        # Format: -session-XXXXX in username part
        if "-session-" in proxy_url:
            # Replace existing session with new random one
            import re
            proxy_url = re.sub(r'-session-[a-z0-9]+', f'-session-{session_id}', proxy_url)
            self.logger.info(f"Generated new proxy session ID: {session_id}")

        return proxy_url

        if self.enabled:
            self.logger.info(f"Proxy middleware enabled: {self._mask_proxy_url()}")
        else:
            self.logger.info("Proxy middleware disabled")

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        proxy_url = crawler.settings.get("PROXY_URL") or os.environ.get("PROXY_URL")
        enabled = crawler.settings.getbool("PROXY_ENABLED", True)

        middleware = cls(proxy_url=proxy_url, enabled=enabled)
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)

        return middleware

    def spider_opened(self, spider):
        """Log when spider opens with clear status."""
        spider.logger.info("=" * 60)
        spider.logger.info("PROXY CONFIGURATION")
        spider.logger.info("=" * 60)
        if self.enabled:
            spider.logger.info(f"  Status: ENABLED")
            spider.logger.info(f"  Proxy URL: {self._mask_proxy_url()}")
        else:
            spider.logger.warning(f"  Status: DISABLED (no PROXY_URL configured)")
        spider.logger.info("=" * 60)

    def process_request(self, request: Request, spider):
        """Add proxy to request if enabled."""
        if self.enabled and self.proxy_url:
            request.meta["proxy"] = self.proxy_url
            self.logger.debug(f"Added proxy to request: {request.url}")

        return None

    def _mask_proxy_url(self) -> str:
        """Mask credentials in proxy URL for logging."""
        if not self.proxy_url:
            return "None"

        # Simple masking of password
        if "@" in self.proxy_url:
            parts = self.proxy_url.split("@")
            auth_parts = parts[0].split(":")
            if len(auth_parts) >= 3:  # protocol://user:pass
                protocol = auth_parts[0]
                user = auth_parts[1].replace("//", "")
                return f"{protocol}://{user}:****@{parts[1]}"

        return self.proxy_url


class RotatingProxyMiddleware:
    """
    Middleware that rotates through multiple proxies.

    Configuration:
    - PROXY_LIST: List of proxy URLs
    - PROXY_ROTATION: 'round-robin' or 'random'
    """

    def __init__(
        self,
        proxy_list: Optional[list] = None,
        rotation: str = "round-robin",
    ):
        self.proxy_list = proxy_list or []
        self.rotation = rotation
        self.current_index = 0
        self.logger = logging.getLogger(__name__)

        if self.proxy_list:
            self.logger.info(
                f"Rotating proxy middleware enabled with {len(self.proxy_list)} proxies"
            )

    @classmethod
    def from_crawler(cls, crawler):
        """Create middleware from crawler settings."""
        proxy_list = crawler.settings.getlist("PROXY_LIST", [])
        rotation = crawler.settings.get("PROXY_ROTATION", "round-robin")

        return cls(proxy_list=proxy_list, rotation=rotation)

    def process_request(self, request: Request, spider):
        """Add rotating proxy to request."""
        if not self.proxy_list:
            return None

        if self.rotation == "random":
            import random
            proxy = random.choice(self.proxy_list)
        else:
            # Round-robin
            proxy = self.proxy_list[self.current_index % len(self.proxy_list)]
            self.current_index += 1

        request.meta["proxy"] = proxy
        self.logger.debug(f"Using proxy: {proxy[:30]}...")

        return None
