from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator


@dataclass
class ProviderResponse:
    content: str = ""
    tool_calls: list[dict] | None = None
    usage: dict = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0})
    raw: dict = field(default_factory=dict)


class BaseProvider(ABC):
    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        self.model = model or self.default_model
        self.api_key = api_key
        self.base_url = base_url

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def available_models(self) -> list[str]: ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> ProviderResponse: ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str | dict, None]: ...

    @abstractmethod
    def format_tools(self, tools_schema: list[dict]) -> list[dict]: ...
