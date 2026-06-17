import json
from typing import AsyncGenerator

import httpx

from zer0code.providers.base import BaseProvider, ProviderResponse


class OllamaProvider(BaseProvider):
    TOOL_CAPABLE_MODELS = frozenset({
        "qwen2.5-coder", "qwen2.5", "llama3.1", "llama3.2", "llama3.3",
        "mistral", "mixtral", "command-r", "command-r-plus", "firefunction",
        "nemotron", "granite3-dense",
    })

    @property
    def default_model(self) -> str:
        return "qwen2.5-coder:14b"

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def available_models(self) -> list[str]:
        return [
            "qwen2.5-coder:14b",
            "qwen2.5-coder:7b",
            "llama3.1:8b",
            "llama3.2:3b",
            "deepseek-coder-v2:16b",
            "codestral:22b",
        ]

    def __init__(self, model: str = "", api_key: str = "", base_url: str = ""):
        super().__init__(model, api_key, base_url)
        self.base_url = base_url or "http://localhost:11434"

    def _model_supports_tools(self) -> bool:
        base_name = self.model.split(":")[0].lower()
        return any(base_name.startswith(m) for m in self.TOOL_CAPABLE_MODELS)

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
            if self._model_supports_tools():
                payload["tools"] = self.format_tools(tools)
            else:
                payload["messages"] = self._inject_tool_prompt(messages, tools)
        return payload

    def _inject_tool_prompt(self, messages: list[dict], tools: list[dict]) -> list[dict]:
        tool_desc_parts = []
        for tool in tools:
            name = tool.get("name", tool.get("function", {}).get("name", "unknown"))
            desc = tool.get("description", tool.get("function", {}).get("description", ""))
            params = tool.get("parameters", tool.get("function", {}).get("parameters", {}))
            tool_desc_parts.append(
                f"- {name}: {desc}\n  Parameters: {json.dumps(params, indent=2)}"
            )

        inject = (
            "You have access to the following tools. To call a tool, respond with a JSON block:\n"
            '```json\n{"tool": "<name>", "arguments": {<args>}}\n```\n\n'
            "Available tools:\n" + "\n".join(tool_desc_parts)
        )

        result = list(messages)
        for i, msg in enumerate(result):
            if msg.get("role") == "system":
                result[i] = {**msg, "content": msg["content"] + "\n\n" + inject}
                return result

        result.insert(0, {"role": "system", "content": inject})
        return result

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

    def _parse_tool_calls(self, msg: dict) -> list[dict] | None:
        raw_calls = msg.get("tool_calls")
        if not raw_calls:
            return self._parse_tool_calls_from_content(msg.get("content", ""))

        parsed = []
        for tc in raw_calls:
            func = tc.get("function", {})
            parsed.append({
                "id": f"ollama_{func.get('name', '')}",
                "name": func.get("name", ""),
                "arguments": json.dumps(func.get("arguments", {})),
            })
        return parsed or None

    def _parse_tool_calls_from_content(self, content: str) -> list[dict] | None:
        if "```json" not in content:
            return None
        try:
            start = content.index("```json") + 7
            end = content.index("```", start)
            block = json.loads(content[start:end].strip())
            if isinstance(block, dict) and "tool" in block:
                return [{
                    "id": f"ollama_{block['tool']}",
                    "name": block["tool"],
                    "arguments": json.dumps(block.get("arguments", {})),
                }]
        except (ValueError, json.JSONDecodeError):
            pass
        return None

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
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            )

        if resp.status_code >= 400:
            raise RuntimeError(f"Ollama API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        msg = data.get("message", {})
        tool_calls = self._parse_tool_calls(msg)

        eval_count = data.get("eval_count", 0)
        prompt_eval_count = data.get("prompt_eval_count", 0)

        return ProviderResponse(
            content=msg.get("content", ""),
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": prompt_eval_count,
                "completion_tokens": eval_count,
            },
            raw=data,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        payload = self._build_payload(messages, tools, stream=True)
        full_content = ""

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        raise RuntimeError(
                            f"Ollama API error ({resp.status_code}): {body.decode()}"
                        )

                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        msg = data.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            full_content += content
                            yield content

                        if msg.get("tool_calls"):
                            for tc in msg["tool_calls"]:
                                func = tc.get("function", {})
                                yield {
                                    "id": f"ollama_{func.get('name', '')}",
                                    "name": func.get("name", ""),
                                    "arguments": json.dumps(func.get("arguments", {})),
                                }

                        if data.get("done", False) and not msg.get("tool_calls"):
                            parsed = self._parse_tool_calls_from_content(full_content)
                            if parsed:
                                for tc in parsed:
                                    yield tc
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            )
