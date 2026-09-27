import json
from typing import AsyncGenerator

import httpx

from truthzero.providers.base import BaseProvider, ProviderResponse


class AnthropicProvider(BaseProvider):
    @property
    def default_model(self) -> str:
        return "claude-sonnet-4-20250514"

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def available_models(self) -> list[str]:
        return [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-haiku-20241022",
        ]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "https://api.anthropic.com/v1"

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _extract_system(self, messages: list[dict]) -> tuple[str, list[dict]]:
        system_parts = []
        filtered = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(msg.get("content", ""))
            else:
                filtered.append(msg)
        return "\n".join(system_parts), filtered

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "tool":
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": content if isinstance(content, str) else json.dumps(content),
                        }
                    ],
                })
            elif role == "assistant" and msg.get("tool_calls"):
                blocks: list[dict] = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in msg["tool_calls"]:
                    args = tc.get("arguments", tc.get("function", {}).get("arguments", "{}"))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": tc.get("name", tc.get("function", {}).get("name", "")),
                        "input": args,
                    })
                converted.append({"role": "assistant", "content": blocks})
            else:
                converted.append({"role": role, "content": content})
        return converted

    def _build_payload(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
        max_tokens: int = 8192,
    ) -> dict:
        system_text, filtered = self._extract_system(messages)
        converted = self._convert_messages(filtered)

        payload: dict = {
            "model": self.model,
            "messages": converted,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if system_text:
            payload["system"] = system_text
        if tools:
            payload["tools"] = self.format_tools(tools)
        return payload

    def format_tools(self, tools_schema: list[dict]) -> list[dict]:
        formatted = []
        for tool in tools_schema:
            if tool.get("type") == "function":
                func = tool["function"]
                formatted.append({
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
            else:
                formatted.append({
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
                })
        return formatted

    def _parse_response(self, data: dict) -> ProviderResponse:
        content_parts = []
        tool_calls = []

        for block in data.get("content", []):
            if block.get("type") == "text":
                content_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "arguments": json.dumps(block.get("input", {})),
                })

        usage_data = data.get("usage", {})
        return ProviderResponse(
            content="".join(content_parts),
            tool_calls=tool_calls or None,
            usage={
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
            },
            raw=data,
        )

    def _handle_error(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise PermissionError(f"Anthropic authentication failed: {response.text}")
        if response.status_code == 429:
            raise RuntimeError(f"Anthropic rate limit exceeded: {response.text}")
        if response.status_code >= 400:
            raise RuntimeError(f"Anthropic API error ({response.status_code}): {response.text}")

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
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=payload,
            )
            self._handle_error(resp)
            return self._parse_response(resp.json())

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        payload = self._build_payload(messages, tools, stream=True)
        current_tool: dict | None = None

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                headers=self._headers(),
                json=payload,
            ) as resp:
                self._handle_error(resp)
                buffer = ""
                event_type = ""
                async for raw_bytes in resp.aiter_bytes():
                    buffer += raw_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if line.startswith("event: "):
                            event_type = line[7:]
                            continue
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        if event_type == "content_block_start":
                            block = data.get("content_block", {})
                            if block.get("type") == "tool_use":
                                current_tool = {
                                    "id": block.get("id", ""),
                                    "name": block.get("name", ""),
                                    "arguments": "",
                                }
                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                            elif delta.get("type") == "input_json_delta":
                                if current_tool is not None:
                                    current_tool["arguments"] += delta.get("partial_json", "")
                        elif event_type == "content_block_stop":
                            if current_tool is not None:
                                yield current_tool
                                current_tool = None
