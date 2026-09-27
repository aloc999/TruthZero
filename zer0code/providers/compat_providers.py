"""OpenAI-compatible providers: Together AI, Gemini, LM Studio, OrcaRouter, GLM.

We're the harness, not the model — any Chat-Completions endpoint with
native tool/function calling works. Together AI is first-class (endpoint
auto-configured); the rest take key + base-URL.
"""
from zer0code.providers.openai_provider import OpenAIProvider


class TogetherProvider(OpenAIProvider):
    @property
    def default_model(self) -> str:
        return "zai-org/GLM-5.3"

    @property
    def name(self) -> str:
        return "together"

    @property
    def available_models(self) -> list[str]:
        return [
            "zai-org/GLM-5.3",
            "Qwen/Qwen3-235B-A22B-fp8",
            "deepseek-ai/DeepSeek-V3",
            "moonshotai/Kimi-K2",
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        ]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "https://api.together.xyz/v1"


class GeminiProvider(OpenAIProvider):
    @property
    def default_model(self) -> str:
        return "gemini-2.0-flash"

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def available_models(self) -> list[str]:
        return ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = (
            base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
        )


class LMStudioProvider(OpenAIProvider):
    @property
    def default_model(self) -> str:
        return "local-model"

    @property
    def name(self) -> str:
        return "lmstudio"

    @property
    def available_models(self) -> list[str]:
        return ["local-model"]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key or "lm-studio", base_url)
        self.base_url = base_url or "http://localhost:1234/v1"


class OrcaRouterProvider(OpenAIProvider):
    @property
    def default_model(self) -> str:
        return "anthropic/claude-sonnet-4"

    @property
    def name(self) -> str:
        return "orcarouter"

    @property
    def available_models(self) -> list[str]:
        return [
            "anthropic/claude-sonnet-4",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
        ]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "https://api.orcarouter.ai/v1"


class GlmProvider(OpenAIProvider):
    """Zhipu Z.AI GLM direct (OpenAI Chat Completions compat).

    Endpoint + key format per Zhipu docs: base
    https://open.bigmodel.cn/api/paas/v4, key ZHIPU_API_KEY
    (Coding Plan: https://api.z.ai/api/coding/paas/v4 — pass as base_url).
    """

    @property
    def default_model(self) -> str:
        return "glm-4.6"

    @property
    def name(self) -> str:
        return "glm"

    @property
    def available_models(self) -> list[str]:
        return ["glm-4.6", "glm-4.5", "glm-4.7", "glm-5", "glm-5.1"]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "https://open.bigmodel.cn/api/paas/v4"
