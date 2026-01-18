"""
Anthropic LLM Provider implementation.

Uses the Anthropic API for classification. Supports Claude models
including claude-3-haiku for cost-effective classification.
"""

from typing import List, Dict, Optional
import aiohttp
import json

from ..base import BaseLLMProvider, LLMError, LLMRateLimitError, LLMAuthError


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic API provider for LLM completions.

    Supports Claude models including:
    - claude-3-haiku-20240307 (fast, cost-effective)
    - claude-3-5-sonnet-20241022 (balanced)
    - claude-3-opus-20240229 (highest quality)
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(
        self, api_key: Optional[str], model: str = "claude-3-haiku-20240307"
    ):
        """
        Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model name (default: claude-3-haiku-20240307)

        Raises:
            LLMAuthError: If api_key is not provided
        """
        super().__init__()
        if not api_key:
            raise LLMAuthError("Anthropic API key is required")

        self.api_key = api_key
        self.model = model

    def get_name(self) -> str:
        """Return provider name."""
        return "anthropic"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 200,
    ) -> str:
        """
        Send a completion request to Anthropic.

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
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        # Anthropic API requires system message to be separate
        system_message = None
        api_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                api_messages.append(msg)

        payload = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_message:
            payload["system"] = system_message

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
                        raise LLMAuthError("Invalid Anthropic API key")

                    if response.status == 429:
                        raise LLMRateLimitError("Anthropic rate limit exceeded")

                    if response.status != 200:
                        raise LLMError(
                            f"Anthropic API error (status {response.status}): {response_text}"
                        )

                    data = json.loads(response_text)
                    # Anthropic returns content as a list of content blocks
                    content_blocks = data.get("content", [])
                    if content_blocks:
                        return content_blocks[0].get("text", "")
                    return ""

            except aiohttp.ClientError as e:
                raise LLMError(f"Network error calling Anthropic API: {e}")
            except json.JSONDecodeError as e:
                raise LLMError(f"Failed to parse Anthropic response: {e}")
            except KeyError as e:
                raise LLMError(f"Unexpected Anthropic response format: {e}")
