"""
In-memory cache for LLM responses.

Caches LLM classification results to avoid duplicate API calls
for the same proposal text.
"""

import hashlib
import time
from typing import Optional, Dict, Any
import logging


class LLMCache:
    """
    Simple in-memory cache for LLM responses with TTL support.

    The cache uses a hash of the input text as the key to avoid
    storing large proposal texts in memory.
    """

    def __init__(self, ttl_seconds: int = 86400, max_size: int = 10000):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default 24 hours)
            max_size: Maximum number of entries to store
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)

        # Statistics
        self.hits = 0
        self.misses = 0

    def _generate_key(self, text: str) -> str:
        """
        Generate a cache key from input text.

        Uses SHA-256 hash to create a fixed-size key.

        Args:
            text: The input text to hash

        Returns:
            Hex digest of the hash
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Get a cached result for the given text.

        Args:
            text: The input text (proposal/description)

        Returns:
            Cached classification result, or None if not found/expired
        """
        key = self._generate_key(text)
        entry = self._cache.get(key)

        if entry is None:
            self.misses += 1
            return None

        # Check if entry has expired
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            self.misses += 1
            return None

        self.hits += 1
        return entry["value"]

    def set(self, text: str, value: Dict[str, Any]) -> None:
        """
        Store a result in the cache.

        Args:
            text: The input text (proposal/description)
            value: The classification result to cache
        """
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        key = self._generate_key(text)
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + self.ttl_seconds,
            "created_at": time.time(),
        }

    def _evict_oldest(self) -> None:
        """Evict the oldest entries to make room for new ones."""
        if not self._cache:
            return

        # Sort by created_at and remove oldest 10%
        sorted_keys = sorted(
            self._cache.keys(), key=lambda k: self._cache[k]["created_at"]
        )
        evict_count = max(1, len(sorted_keys) // 10)

        for key in sorted_keys[:evict_count]:
            del self._cache[key]

        self.logger.debug(f"Evicted {evict_count} oldest cache entries")

    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            "entries": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate_percent": round(hit_rate, 2),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }
