"""
Base class for LLM providers.

Defines the interface that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
import logging


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All providers (OpenAI, Anthropic, Ollama) must implement this interface.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 200,
    ) -> str:
        """
        Send a completion request to the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            The LLM's response text

        Raises:
            LLMError: If the request fails after retries
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get the provider name.

        Returns:
            Provider name string (e.g., 'openai', 'anthropic', 'ollama')
        """
        pass

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.

        This is a rough estimate using ~4 characters per token.

        Args:
            text: The text to estimate

        Returns:
            Estimated token count
        """
        return len(text) // 4 + 1

    async def complete_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 200,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ) -> str:
        """
        Send a completion request with retry logic.

        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            max_retries: Maximum number of retry attempts
            backoff_base: Base delay for exponential backoff (seconds)

        Returns:
            The LLM's response text

        Raises:
            LLMError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.complete(messages, temperature, max_tokens)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = backoff_base * (2**attempt)
                    self.logger.warning(
                        f"LLM request failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        f"LLM request failed after {max_retries} attempts: {e}"
                    )

        raise LLMError(f"LLM request failed after {max_retries} retries: {last_error}")


class LLMError(Exception):
    """Exception raised for LLM-related errors."""

    pass


class LLMRateLimitError(LLMError):
    """Exception raised when rate limited by the LLM provider."""

    pass


class LLMAuthError(LLMError):
    """Exception raised for authentication errors."""

    pass
