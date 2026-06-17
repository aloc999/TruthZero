import json
from typing import AsyncGenerator

import httpx

from zer0code.providers.base import BaseProvider, ProviderResponse


class OpenAIProvider(BaseProvider):
    @property
    def default_model(self) -> str:
        return "gpt-4o"

    @property
    def name(self) -> str:
        return "openai"

    @property
    def available_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "https://api.openai.com/v1"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = self.format_tools(tools)
        return payload

    def format_tools(self, tools_schema: list[dict]) -> list[dict]:
        formatted = []
        for tool in tools_schema:
            if tool.get("type") == "function":
                formatted.append(tool)
            else:
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
                    },
                })
        return formatted

    def _parse_tool_calls(self, raw_tool_calls: list[dict]) -> list[dict]:
        parsed = []
        for tc in raw_tool_calls:
            parsed.append({
                "id": tc.get("id", ""),
                "name": tc.get("function", {}).get("name", ""),
                "arguments": tc.get("function", {}).get("arguments", "{}"),
            })
        return parsed

    def _handle_error(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise PermissionError(f"OpenAI authentication failed: {response.text}")
        if response.status_code == 429:
            raise RuntimeError(f"OpenAI rate limit exceeded: {response.text}")
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI API error ({response.status_code}): {response.text}")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> ProviderResponse:
        if stream:
            chunks: list[str] = []
            tool_calls_agg: list[dict] = []
            async for chunk in self.stream_chat(messages, tools):
                if isinstance(chunk, str):
                    chunks.append(chunk)
                elif isinstance(chunk, dict):
                    tool_calls_agg.append(chunk)
            return ProviderResponse(
                content="".join(chunks),
                tool_calls=tool_calls_agg or None,
                usage={"prompt_tokens": 0, "completion_tokens": 0},
                raw={},
            )

        payload = self._build_payload(messages, tools, stream=False)
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            self._handle_error(resp)
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        usage_data = data.get("usage", {})

        tool_calls = None
        if msg.get("tool_calls"):
            tool_calls = self._parse_tool_calls(msg["tool_calls"])

        return ProviderResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": usage_data.get("prompt_tokens", 0),
                "completion_tokens": usage_data.get("completion_tokens", 0),
            },
            raw=data,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        payload = self._build_payload(messages, tools, stream=True)
        tool_calls_buffer: dict[int, dict] = {}

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                self._handle_error(resp)
                buffer = ""
                async for raw_bytes in resp.aiter_bytes():
                    buffer += raw_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
                        if delta.get("tool_calls"):
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                if idx not in tool_calls_buffer:
                                    tool_calls_buffer[idx] = {
                                        "id": tc_delta.get("id", ""),
                                        "name": tc_delta.get("function", {}).get("name", ""),
                                        "arguments": "",
                                    }
                                if tc_delta.get("function", {}).get("name"):
                                    tool_calls_buffer[idx]["name"] = tc_delta["function"]["name"]
                                if tc_delta.get("id"):
                                    tool_calls_buffer[idx]["id"] = tc_delta["id"]
                                if tc_delta.get("function", {}).get("arguments"):
                                    tool_calls_buffer[idx]["arguments"] += tc_delta["function"]["arguments"]

        for idx in sorted(tool_calls_buffer):
            yield tool_calls_buffer[idx]
