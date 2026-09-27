from zer0code.providers.base import BaseProvider, ProviderResponse
from zer0code.providers.openai_provider import OpenAIProvider
from zer0code.providers.anthropic_provider import AnthropicProvider
from zer0code.providers.ollama_provider import OllamaProvider
from zer0code.providers.deepseek_provider import DeepSeekProvider
from zer0code.providers.compat_providers import (
    TogetherProvider, GeminiProvider, LMStudioProvider, OrcaRouterProvider,
)

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "deepseek": DeepSeekProvider,
    "together": TogetherProvider,
    "gemini": GeminiProvider,
    "lmstudio": LMStudioProvider,
    "orcarouter": OrcaRouterProvider,
}


def get_provider(name: str, **kwargs) -> BaseProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](**kwargs)
