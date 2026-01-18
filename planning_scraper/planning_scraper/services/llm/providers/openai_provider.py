"""
OpenAI LLM Provider implementation.

Uses the OpenAI API for classification. Default model is gpt-4o-mini
which offers good performance at low cost (~$0.15/1M tokens).
"""

from typing import List, Dict, Optional
import aiohttp
import json

from ..base import BaseLLMProvider, LLMError, LLMRateLimitError, LLMAuthError


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider for LLM completions.

    Supports all OpenAI chat models including:
    - gpt-4o-mini (recommended for cost efficiency)
    - gpt-4o (higher quality, higher cost)
    - gpt-4-turbo
    """

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini"):
        """
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)

        Raises:
            LLMAuthError: If api_key is not provided
        """
        super().__init__()
        if not api_key:
            raise LLMAuthError("OpenAI API key is required")

        self.api_key = api_key
        self.model = model

    def get_name(self) -> str:
        """Return provider name."""
        return "openai"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 200,
    ) -> str:
        """
        Send a completion request to OpenAI.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response

        Returns:
            The assistant's response text

        Raises:
            LLMError: If the request fails
            LLMRateLimitError: If rate limited
            LLMAuthError: If authentication fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    response_text = await response.text()

                    if response.status == 401:
                        raise LLMAuthError("Invalid OpenAI API key")

                    if response.status == 429:
                        raise LLMRateLimitError("OpenAI rate limit exceeded")

                    if response.status != 200:
                        raise LLMError(
                            f"OpenAI API error (status {response.status}): {response_text}"
                        )

                    data = json.loads(response_text)
                    return data["choices"][0]["message"]["content"]

            except aiohttp.ClientError as e:
                raise LLMError(f"Network error calling OpenAI API: {e}")
            except json.JSONDecodeError as e:
                raise LLMError(f"Failed to parse OpenAI response: {e}")
            except KeyError as e:
                raise LLMError(f"Unexpected OpenAI response format: {e}")
