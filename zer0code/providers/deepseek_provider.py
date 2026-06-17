import json
from typing import AsyncGenerator

import httpx

from zer0code.providers.openai_provider import OpenAIProvider
from zer0code.providers.base import ProviderResponse


class DeepSeekProvider(OpenAIProvider):
    @property
    def default_model(self) -> str:
        return "deepseek-chat"

    @property
    def name(self) -> str:
        return "deepseek"

    @property
    def available_models(self) -> list[str]:
        return ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro"]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "https://api.deepseek.com/v1"

    def _handle_error(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise PermissionError(f"DeepSeek authentication failed: {response.text}")
        if response.status_code == 429:
            raise RuntimeError(f"DeepSeek rate limit exceeded: {response.text}")
        if response.status_code >= 400:
            raise RuntimeError(f"DeepSeek API error ({response.status_code}): {response.text}")
