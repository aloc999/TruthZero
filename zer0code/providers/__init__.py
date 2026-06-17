from zer0code.providers.base import BaseProvider, ProviderResponse
from zer0code.providers.openai_provider import OpenAIProvider
from zer0code.providers.anthropic_provider import AnthropicProvider
from zer0code.providers.ollama_provider import OllamaProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}


def get_provider(name: str, **kwargs) -> BaseProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](**kwargs)
