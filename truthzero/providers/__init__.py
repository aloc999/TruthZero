from truthzero.providers.anthropic_provider import AnthropicProvider
from truthzero.providers.base import BaseProvider, ProviderResponse
from truthzero.providers.compat_providers import (
    GeminiProvider,
    GlmProvider,
    LMStudioProvider,
    OrcaRouterProvider,
    TogetherProvider,
)
from truthzero.providers.deepseek_provider import DeepSeekProvider
from truthzero.providers.ollama_provider import OllamaProvider
from truthzero.providers.openai_provider import OpenAIProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "deepseek": DeepSeekProvider,
    "together": TogetherProvider,
    "gemini": GeminiProvider,
    "lmstudio": LMStudioProvider,
    "orcarouter": OrcaRouterProvider,
    "glm": GlmProvider,
}


def get_provider(name: str, **kwargs) -> BaseProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](**kwargs)

__all__ = [
    "AnthropicProvider",
    "BaseProvider",
    "ProviderResponse",
    "GeminiProvider",
    "GlmProvider",
    "LMStudioProvider",
    "OrcaRouterProvider",
    "TogetherProvider",
    "DeepSeekProvider",
    "OllamaProvider",
    "OpenAIProvider",
]
