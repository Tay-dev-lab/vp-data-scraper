"""
Ollama LLM Provider implementation.

Uses a local Ollama server for classification. Free and private,
but requires Ollama to be installed and running locally.
"""

from typing import List, Dict, Optional
import aiohttp
import json

from ..base import BaseLLMProvider, LLMError


class OllamaProvider(BaseLLMProvider):
    """
    Ollama local LLM provider.

    Supports any model available in Ollama including:
    - llama3.1 (recommended for good quality)
    - mistral (fast, good for simple tasks)
    - codellama (code-focused)

    Requires Ollama to be installed and running locally.
    See: https://ollama.ai
    """

    def __init__(
        self, base_url: str = "http://localhost:11434", model: str = "llama3.1"
    ):
        """
        Initialize the Ollama provider.

        Args:
            base_url: Ollama server URL (default: http://localhost:11434)
            model: Model name (default: llama3.1)
        """
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.model = model

    def get_name(self) -> str:
        """Return provider name."""
        return "ollama"

    async def complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 200,
    ) -> str:
        """
        Send a completion request to Ollama.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens in response (Ollama uses num_predict)

        Returns:
            The assistant's response text

        Raises:
            LLMError: If the request fails
        """
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),  # Longer timeout for local
                ) as response:
                    response_text = await response.text()

                    if response.status != 200:
                        raise LLMError(
                            f"Ollama API error (status {response.status}): {response_text}"
                        )

                    data = json.loads(response_text)
                    return data.get("message", {}).get("content", "")

            except aiohttp.ClientConnectorError:
                raise LLMError(
                    f"Could not connect to Ollama at {self.base_url}. "
                    f"Is Ollama running? Try: ollama serve"
                )
            except aiohttp.ClientError as e:
                raise LLMError(f"Network error calling Ollama API: {e}")
            except json.JSONDecodeError as e:
                raise LLMError(f"Failed to parse Ollama response: {e}")
