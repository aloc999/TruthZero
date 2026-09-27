from truthzero.providers.base import BaseProvider, ProviderResponse
from truthzero.providers.openai_provider import OpenAIProvider
from truthzero.providers.anthropic_provider import AnthropicProvider
from truthzero.providers.ollama_provider import OllamaProvider
from truthzero.providers.deepseek_provider import DeepSeekProvider
from truthzero.providers.compat_providers import (
    TogetherProvider, GeminiProvider, LMStudioProvider, OrcaRouterProvider,
    GlmProvider,
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
    "glm": GlmProvider,
}


def get_provider(name: str, **kwargs) -> BaseProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name](**kwargs)
