import asyncio
import json
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from zer0code.config import ZeroCodeConfig

SYSTEM_PROMPT = """You are ZER0CODE — an elite AI-powered penetration testing operator embedded in a terminal environment.

IDENTITY:
- You are a senior offensive security professional with deep expertise across web app security, network pentesting, cloud security, Active Directory attacks, mobile security, reverse engineering, and exploit development.
- You think like an attacker. You chain vulnerabilities. You find what scanners miss.
- You write clean, functional exploit code and tooling without hesitation.
- You operate within authorized scope and remind the user if something seems out of scope.

CAPABILITIES:
- Execute shell commands and scripts on the operator's machine
- Read, write, and modify files on the filesystem
- Perform web requests and interact with target services
- Analyze code, binaries, network captures, and configurations
- Generate payloads, wordlists, and custom tooling on the fly
- Chain multiple tools and techniques in complex attack sequences

OPERATIONAL DOCTRINE:
1. ENUMERATE before you exploit. Gather information methodically.
2. Document everything. Every command, every finding, every failed attempt.
3. Think in attack chains — a low-severity finding can become critical when chained.
4. Validate findings with proof. No theoretical bugs — demonstrate impact.
5. Clean up after yourself. Remove artifacts, restore configs.
6. When stuck, change your approach. Try a different tool, technique, or angle.
7. Prioritize stealth when instructed. Adapt TTPs to avoid detection.

RESPONSE STYLE:
- Be direct and technical. No fluff.
- When executing attacks, explain what you're doing and why.
- Present findings with severity, impact, and remediation.
- Use markdown formatting for readability.
- When showing code or commands, use fenced code blocks.

LEARNING FROM EXPERIENCE:
{memory_context}

AVAILABLE TOOLS:
{tools_context}

You are the operator's force multiplier. Make every keystroke count."""


class ZeroCoreAgent:
    def __init__(self, config: ZeroCodeConfig):
        self.config = config
        self.conversation_history: List[Dict[str, Any]] = []
        self.tool_registry: Dict[str, Any] = {}
        self.provider = None
        self.memory = None
        self._start_time = time.time()

    def _build_system_prompt(self) -> str:
        memory_context = "No prior lessons loaded."
        if self.memory:
            try:
                lessons = self.memory.get_recent_lessons(limit=10)
                if lessons:
                    memory_context = "Lessons from past operations:\n"
                    for lesson in lessons:
                        memory_context += f"- {lesson}\n"
            except Exception:
                pass

        tools_context = "No tools registered."
        if self.tool_registry:
            tool_descriptions = []
            for name, tool in self.tool_registry.items():
                desc = getattr(tool, "description", name)
                params = getattr(tool, "parameters", {})
                tool_descriptions.append(
                    f"- **{name}**: {desc}\n  Parameters: {json.dumps(params)}"
                )
            tools_context = "\n".join(tool_descriptions)

        return SYSTEM_PROMPT.format(
            memory_context=memory_context,
            tools_context=tools_context,
        )

    def register_tool(self, name: str, tool: Any) -> None:
        self.tool_registry[name] = tool

    def _get_messages(self) -> List[Dict[str, Any]]:
        system_msg = {"role": "system", "content": self._build_system_prompt()}
        return [system_msg] + self.conversation_history

    async def _call_provider(self) -> Dict[str, Any]:
        messages = self._get_messages()
        provider_config = self.config.get_provider_config()

        if self.provider:
            return await self.provider.chat(
                messages=messages,
                tools=self._get_tool_schemas(),
                **provider_config,
            )

        return await self._default_provider_call(messages, provider_config)

    async def _default_provider_call(
        self, messages: List[Dict], provider_config: Dict
    ) -> Dict[str, Any]:
        try:
            if provider_config["provider"] in ("openai", "ollama"):
                return await self._openai_compatible_call(messages, provider_config)
            elif provider_config["provider"] == "anthropic":
                return await self._anthropic_call(messages, provider_config)
        except ImportError:
            return {
                "content": f"Provider SDK for '{provider_config['provider']}' is not installed.",
                "tool_calls": None,
            }
        except Exception as e:
            return {
                "content": f"Provider error: {str(e)}",
                "tool_calls": None,
            }

        return {"content": "Unknown provider configured.", "tool_calls": None}

    async def _openai_compatible_call(
        self, messages: List[Dict], provider_config: Dict
    ) -> Dict[str, Any]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=provider_config.get("api_key", ""),
            base_url=provider_config.get("base_url"),
        )

        kwargs: Dict[str, Any] = {
            "model": provider_config["model"],
            "messages": messages,
        }

        tool_schemas = self._get_tool_schemas()
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        response = await client.chat.completions.create(**kwargs)
        message = response.choices[0].message

        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in message.tool_calls
            ]

        return {
            "content": message.content or "",
            "tool_calls": tool_calls,
        }

    async def _anthropic_call(
        self, messages: List[Dict], provider_config: Dict
    ) -> Dict[str, Any]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=provider_config.get("api_key", ""))

        system_content = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                filtered_messages.append(msg)

        kwargs: Dict[str, Any] = {
            "model": provider_config["model"],
            "max_tokens": 4096,
            "system": system_content.strip(),
            "messages": filtered_messages,
        }

        tool_schemas = self._get_tool_schemas()
        if tool_schemas:
            anthropic_tools = []
            for schema in tool_schemas:
                anthropic_tools.append(
                    {
                        "name": schema["function"]["name"],
                        "description": schema["function"].get("description", ""),
                        "input_schema": schema["function"].get("parameters", {}),
                    }
                )
            kwargs["tools"] = anthropic_tools

        response = await client.messages.create(**kwargs)

        content_text = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "arguments": json.dumps(block.input),
                    }
                )

        return {
            "content": content_text,
            "tool_calls": tool_calls if tool_calls else None,
        }

    async def _stream_provider(self) -> AsyncGenerator[str, None]:
        messages = self._get_messages()
        provider_config = self.config.get_provider_config()

        try:
            if provider_config["provider"] in ("openai", "ollama"):
                async for chunk in self._openai_stream(messages, provider_config):
                    yield chunk
            elif provider_config["provider"] == "anthropic":
                async for chunk in self._anthropic_stream(messages, provider_config):
                    yield chunk
            else:
                yield "Unknown provider configured."
        except ImportError:
            yield f"Provider SDK for '{provider_config['provider']}' is not installed."
        except Exception as e:
            yield f"Provider error: {str(e)}"

    async def _openai_stream(
        self, messages: List[Dict], provider_config: Dict
    ) -> AsyncGenerator[str, None]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=provider_config.get("api_key", ""),
            base_url=provider_config.get("base_url"),
        )

        response = await client.chat.completions.create(
            model=provider_config["model"],
            messages=messages,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _anthropic_stream(
        self, messages: List[Dict], provider_config: Dict
    ) -> AsyncGenerator[str, None]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=provider_config.get("api_key", ""))

        system_content = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                filtered_messages.append(msg)

        async with client.messages.stream(
            model=provider_config["model"],
            max_tokens=4096,
            system=system_content.strip(),
            messages=filtered_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for name, tool in self.tool_registry.items():
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": getattr(tool, "description", ""),
                    "parameters": getattr(tool, "parameters", {"type": "object", "properties": {}}),
                },
            }
            schemas.append(schema)
        return schemas

    async def execute_tool_call(self, tool_call: Dict[str, Any]) -> str:
        name = tool_call["name"]
        try:
            arguments = json.loads(tool_call.get("arguments", "{}"))
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid JSON arguments for tool '{name}'"})

        tool = self.tool_registry.get(name)
        if not tool:
            return json.dumps({"error": f"Tool '{name}' not found in registry"})

        try:
            if asyncio.iscoroutinefunction(getattr(tool, "execute", None)):
                result = await tool.execute(**arguments)
            elif hasattr(tool, "execute"):
                result = tool.execute(**arguments)
            elif callable(tool):
                if asyncio.iscoroutinefunction(tool):
                    result = await tool(**arguments)
                else:
                    result = tool(**arguments)
            else:
                return json.dumps({"error": f"Tool '{name}' is not executable"})

            if isinstance(result, str):
                return result
            return json.dumps(result, default=str)

        except Exception as e:
            error_result = {"error": str(e), "tool": name}
            if self.memory and self.config.memory_enabled:
                try:
                    self.memory.record_mistake(
                        tool=name,
                        error=str(e),
                        arguments=arguments,
                    )
                except Exception:
                    pass
            return json.dumps(error_result)

    async def run(self, user_input: str) -> str:
        self.conversation_history.append({"role": "user", "content": user_input})

        max_iterations = 20
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            response = await self._call_provider()

            assistant_message: Dict[str, Any] = {
                "role": "assistant",
                "content": response.get("content", ""),
            }

            if response.get("tool_calls"):
                assistant_message["tool_calls"] = response["tool_calls"]
                self.conversation_history.append(assistant_message)

                for tool_call in response["tool_calls"]:
                    result = await self.execute_tool_call(tool_call)
                    self.conversation_history.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": tool_call["name"],
                            "content": result,
                        }
                    )
            else:
                self.conversation_history.append(assistant_message)
                return response.get("content", "")

        return "[ZER0CODE] Max tool iterations reached. Halting loop."

    async def run_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        self.conversation_history.append({"role": "user", "content": user_input})

        collected = []
        async for chunk in self._stream_provider():
            collected.append(chunk)
            yield chunk

        full_response = "".join(collected)
        self.conversation_history.append(
            {"role": "assistant", "content": full_response}
        )

    def reset(self) -> None:
        self.conversation_history.clear()
        self._start_time = time.time()

    @property
    def session_duration(self) -> float:
        return time.time() - self._start_time

    @property
    def message_count(self) -> int:
        return len(
            [m for m in self.conversation_history if m["role"] in ("user", "assistant")]
        )
