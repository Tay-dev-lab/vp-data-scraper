"""
LLM Service for planning application classification.

Provides model-agnostic LLM integration for classifying planning applications
to identify new build and conversion developments.
"""

from .base import BaseLLMProvider
from .classifier import PlanningApplicationClassifier
from .cache import LLMCache

# Provider factory
_provider_instance = None


def get_llm_provider(provider_name: str, settings: dict) -> BaseLLMProvider:
    """
    Factory function to get the appropriate LLM provider.

    Args:
        provider_name: Name of the provider ('openai', 'anthropic', 'ollama')
        settings: Scrapy settings dictionary with API keys and configuration

    Returns:
        An instance of the appropriate LLM provider

    Raises:
        ValueError: If provider_name is not supported
    """
    global _provider_instance

    # Return cached instance if available and same provider
    if _provider_instance and _provider_instance.get_name() == provider_name:
        return _provider_instance

    provider_name = provider_name.lower()

    if provider_name == "openai":
        from .providers.openai_provider import OpenAIProvider

        _provider_instance = OpenAIProvider(
            api_key=settings.get("LLM_API_KEY") or settings.get("OPENAI_API_KEY"),
            model=settings.get("LLM_MODEL", "gpt-4o-mini"),
        )
    elif provider_name == "anthropic":
        from .providers.anthropic_provider import AnthropicProvider

        _provider_instance = AnthropicProvider(
            api_key=settings.get("ANTHROPIC_API_KEY"),
            model=settings.get("LLM_MODEL", "claude-3-haiku-20240307"),
        )
    elif provider_name == "ollama":
        from .providers.ollama_provider import OllamaProvider

        _provider_instance = OllamaProvider(
            base_url=settings.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=settings.get("LLM_MODEL", "llama3.1"),
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. "
            f"Supported providers: openai, anthropic, ollama"
        )

    return _provider_instance


__all__ = [
    "BaseLLMProvider",
    "PlanningApplicationClassifier",
    "LLMCache",
    "get_llm_provider",
]
