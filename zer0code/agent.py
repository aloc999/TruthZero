import asyncio
import hashlib
import json
import os
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from zer0code.config import ZeroCodeConfig
from zer0code.cost import CostTracker
from zer0code.context import ContextCompactor, ProjectContext
from zer0code.hooks import AutoLintHook, HookManager
from zer0code.memory import LoopDetector, MemoryStore, ReflectionEngine
from zer0code.permissions import PermissionManager
from zer0code.providers import get_provider
from zer0code.providers.base import BaseProvider, ProviderResponse
from zer0code.session import SessionManager
from zer0code.tools.base import BaseTool, ToolResult
from zer0code.retry import RetryHandler, RetryConfig
from zer0code.vision import VisionInput
from zer0code.rollback import RollbackManager
from zer0code.notifications import NotificationManager
from zer0code.branching import ConversationBrancher
from zer0code.export import SessionExporter
from zer0code.file_index import FileIndex


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
- Learn from past mistakes and adapt strategies

OPERATIONAL DOCTRINE:
1. ENUMERATE before you exploit. Gather information methodically.
2. Document everything. Every command, every finding, every failed attempt.
3. Think in attack chains — a low-severity finding can become critical when chained.
4. Validate findings with proof. No theoretical bugs — demonstrate impact.
5. Clean up after yourself. Remove artifacts, restore configs.
6. When stuck, change your approach. Try a different tool, technique, or angle.
7. Prioritize stealth when instructed. Adapt TTPs to avoid detection.
8. When a tool fails repeatedly, switch to an alternative approach entirely.
9. Execute multiple independent tool calls in parallel when possible.

RESPONSE STYLE:
- Be direct and technical. No fluff.
- When executing attacks, explain what you're doing and why.
- Present findings with severity, impact, and remediation.
- Use markdown formatting for readability.
- When showing code or commands, use fenced code blocks.

{project_context}

{memory_context}

{loop_warning}

{confidence_assessment}

{file_tree_context}

{git_context}

{custom_prompt}

{strategy_hint}"""


class ZeroCoreAgent:
    def __init__(self, config: ZeroCodeConfig):
        self.config = config
        self.conversation_history: List[Dict[str, Any]] = []
        self.tool_registry: Dict[str, BaseTool] = {}
        self.provider: Optional[BaseProvider] = None
        self.cost_tracker = CostTracker()
        self.loop_detector = LoopDetector()
        self.permissions: Optional[PermissionManager] = None
        self.memory_store: Optional[MemoryStore] = None
        self.reflection: Optional[ReflectionEngine] = None
        self.session_manager: Optional[SessionManager] = None
        self.session_id: Optional[str] = None
        self.project_context = ProjectContext()
        self.compactor: Optional[ContextCompactor] = None
        self.hooks = HookManager()
        self.mcp_tools: Dict[str, Any] = {}
        self._start_time = time.time()
        self._on_tool_call: Optional[Callable] = None
        self._on_tool_result: Optional[Callable] = None
        self.retry_handler = RetryHandler()
        self.rollback = RollbackManager()
        self.notifications = NotificationManager()
        self.brancher = ConversationBrancher()
        self.exporter = SessionExporter()
        self.token_budget: float = 0.0
        self._context_max_tokens: int = 128000
        self.file_index: Optional[FileIndex] = None
        self.max_turns: int = 25
        self._step_mode: bool = False
        self._custom_prompt: str = ""
        self._diff_approval: bool = False

    async def initialize(self):
        provider_config = self.config.get_provider_config()
        self.provider = get_provider(
            self.config.provider,
            model=self.config.model,
            api_key=provider_config.get("api_key", ""),
            base_url=provider_config.get("base_url", ""),
        )
        self.compactor = ContextCompactor(provider=self.provider)

        if self.config.memory_enabled:
            self.memory_store = MemoryStore(self.config.memory_db_path)
            await self.memory_store.init()
            self.reflection = ReflectionEngine(self.memory_store)

        self.project_context.detect_project_root()
        self.project_context.load_instructions()
        self.project_context.detect_tech_stack()

        self.hooks.register("post_tool", "auto_lint", AutoLintHook.on_file_write)

        self.file_index = FileIndex(self.project_context.project_root or ".")
        self.file_index.scan()
        self._context_max_tokens = self.config.max_context_tokens
        self.max_turns = getattr(self.config, 'max_turns', 25) or 25

    def register_tool(self, tool: BaseTool) -> None:
        instance = tool() if isinstance(tool, type) else tool
        self.tool_registry[instance.name] = instance

    def register_tools(self, tools: List) -> None:
        for tool in tools:
            self.register_tool(tool)

    def register_mcp_tools(self, schemas: List[Dict], call_fn: Callable) -> None:
        for schema in schemas:
            func = schema.get("function", {})
            name = func.get("name", "")
            if name:
                self.mcp_tools[name] = {
                    "schema": schema,
                    "call_fn": call_fn,
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                }

    def set_callbacks(
        self,
        on_tool_call: Optional[Callable] = None,
        on_tool_result: Optional[Callable] = None,
    ):
        self._on_tool_call = on_tool_call
        self._on_tool_result = on_tool_result

    def _build_system_prompt(self) -> str:
        memory_context = ""
        if self.reflection:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    memory_context = ""
                else:
                    memory_context = loop.run_until_complete(
                        self.reflection.get_context_memories("")
                    )
            except Exception:
                pass

        strategy_hint = ""
        if self.reflection:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if not loop.is_running():
                    strategy_hint = loop.run_until_complete(self.reflection.replay_strategy(""))
            except Exception:
                pass

        project_context = self.project_context.get_context_prompt()

        loop_warning = ""
        if self.loop_detector.is_looping():
            loop_warning = f"WARNING: {self.loop_detector.get_loop_info()}"

        confidence_assessment = ""
        if self.reflection and len(self.conversation_history) > 10:
            try:
                confidence_assessment = "SELF-ASSESSMENT: Monitor for repeated patterns."
            except Exception:
                pass

        file_tree_context = ""
        if self.file_index and self.file_index.file_count > 0:
            file_tree_context = self.file_index.get_context_prompt()

        git_context = ""
        try:
            import asyncio, subprocess
            branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=3, cwd=self.project_context.project_root or ".").stdout.strip()
            status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=3, cwd=self.project_context.project_root or ".").stdout.strip()
            if branch:
                git_context = f"GIT STATE:\n  Branch: {branch}"
                if status:
                    git_context += f"\n  Changed files:\n{status}"
        except Exception:
            pass

        custom_prompt = ""
        if self._custom_prompt:
            custom_prompt = f"ADDITIONAL INSTRUCTIONS:\n{self._custom_prompt}"

        return SYSTEM_PROMPT.format(
            project_context=project_context,
            memory_context=memory_context,
            loop_warning=loop_warning,
            confidence_assessment=confidence_assessment,
            file_tree_context=file_tree_context,
            git_context=git_context,
            custom_prompt=custom_prompt,
            strategy_hint=strategy_hint,
        )

    def _get_messages(self) -> List[Dict[str, Any]]:
        system_msg = {"role": "system", "content": self._build_system_prompt()}
        messages = [system_msg] + self.conversation_history
        return self._sanitize_messages(messages)

    def _sanitize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for msg in messages:
            m = dict(msg)
            content = m.get("content")
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "image_url":
                            text_parts.append("[image]")
                    elif isinstance(block, str):
                        text_parts.append(block)
                m["content"] = "\n".join(text_parts) if text_parts else ""
            elif content is None:
                m["content"] = ""
            if "tool_calls" in m and m["tool_calls"]:
                fixed_calls = []
                for tc in m["tool_calls"]:
                    if isinstance(tc, dict) and "type" not in tc:
                        fixed_calls.append({
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.get("name", ""),
                                "arguments": tc.get("arguments", "{}"),
                            },
                        })
                    else:
                        fixed_calls.append(tc)
                m["tool_calls"] = fixed_calls
            elif "tool_calls" in m and not m["tool_calls"]:
                del m["tool_calls"]
            cleaned.append(m)

        result = []
        i = 0
        while i < len(cleaned):
            msg = cleaned[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tc_ids = set()
                for tc in msg["tool_calls"]:
                    tc_id = tc.get("id", "") or tc.get("function", {}).get("name", "")
                    tc_ids.add(tc_id)
                tool_results = []
                j = i + 1
                while j < len(cleaned) and cleaned[j].get("role") == "tool":
                    tool_results.append(cleaned[j])
                    j += 1
                if tool_results:
                    result.append(msg)
                    result.extend(tool_results)
                    i = j
                else:
                    m_no_tc = dict(msg)
                    del m_no_tc["tool_calls"]
                    if m_no_tc.get("content"):
                        result.append(m_no_tc)
                    i += 1
            elif msg.get("role") == "tool":
                i += 1
            else:
                result.append(msg)
                i += 1

        return result

    def _get_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for name, tool in self.tool_registry.items():
            schemas.append(tool.schema() if hasattr(tool, "schema") else {
                "type": "function",
                "function": {
                    "name": name,
                    "description": getattr(tool, "description", ""),
                    "parameters": getattr(tool, "parameters", {"type": "object", "properties": {}}),
                },
            })
        for name, mcp_tool in self.mcp_tools.items():
            schemas.append(mcp_tool["schema"])
        return schemas

    async def execute_tool_call(self, tool_call: Dict[str, Any]) -> ToolResult:
        name = tool_call.get("name", "")
        if name in ("write_file", "edit_file") and "file_path" in str(tool_call.get("arguments", "")):
            try:
                args_dict = json.loads(tool_call.get("arguments", "{}"))
                fp = args_dict.get("file_path", args_dict.get("filePath", ""))
                if fp:
                    self.rollback.snapshot(fp)
            except Exception:
                pass
        if self._diff_approval and name == "edit_file" and self._on_tool_call:
            try:
                args_dict = json.loads(tool_call.get("arguments", "{}"))
                old_s = args_dict.get("old_string", "")[:200]
                new_s = args_dict.get("new_string", "")[:200]
                if old_s or new_s:
                    pass
            except Exception:
                pass
        try:
            arguments = json.loads(tool_call.get("arguments", "{}"))
        except json.JSONDecodeError:
            return ToolResult(output="", success=False, error=f"Invalid JSON arguments for tool '{name}'")

        if self.reflection:
            try:
                warning = await self.reflection.proactive_warning(name, arguments)
                if warning and self._on_tool_call:
                    pass
            except Exception:
                pass

        if self.permissions:
            approved, reason = await self.permissions.check_permission(name, arguments)
            if not approved:
                return ToolResult(output="", success=False, error=f"Permission denied: {reason}")

        if self._on_tool_call:
            try:
                self._on_tool_call(name, arguments)
            except Exception:
                pass

        await self.hooks.trigger("pre_tool", tool_name=name, args=arguments)

        start_time = time.monotonic()

        if name in self.mcp_tools:
            try:
                result_text = await self.mcp_tools[name]["call_fn"](name, arguments)
                result = ToolResult(output=result_text, success=True)
            except Exception as e:
                result = ToolResult(output="", success=False, error=str(e))
        elif name in self.tool_registry:
            tool = self.tool_registry[name]
            try:
                result = await tool.execute(**arguments)
            except Exception as e:
                result = ToolResult(output="", success=False, error=str(e))
        else:
            result = ToolResult(output="", success=False, error=f"Tool '{name}' not found")

        duration_ms = int((time.monotonic() - start_time) * 1000)

        result_hash = hashlib.md5(result.output[:500].encode()).hexdigest()[:12] if result.output else ""
        self.loop_detector.record_call(name, arguments, result_hash)

        if self.reflection:
            if result.success:
                await self.reflection.analyze_tool_success(name, arguments, result.output, "")
            else:
                await self.reflection.analyze_tool_failure(name, arguments, result.error or "", "")
                try:
                    await self.reflection.root_cause_analysis(name, result.error or "", arguments, "")
                except Exception:
                    pass

            if self.memory_store and self.session_id:
                await self.memory_store.add_episode(
                    self.session_id, name, arguments,
                    result.output[:500] if result.output else (result.error or ""),
                    result.success, "", duration_ms,
                )

        hook_results = await self.hooks.trigger(
            "post_tool", tool_name=name, args=arguments,
            file_path=arguments.get("file_path", arguments.get("filePath", "")),
        )
        hook_messages = [hr.message for hr in hook_results if hr.message]

        if self._on_tool_result:
            try:
                self._on_tool_result(name, result, hook_messages)
            except Exception:
                pass

        if hook_messages:
            result.output += "\n\n[Lint Output]\n" + "\n".join(hook_messages)

        return result

    async def _execute_tools_parallel(self, tool_calls: List[Dict]) -> List[Dict]:
        tasks = [self.execute_tool_call(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        tool_messages = []
        for tc, result in zip(tool_calls, results):
            if isinstance(result, Exception):
                output = json.dumps({"error": str(result)})
            elif isinstance(result, ToolResult):
                if result.success:
                    output = result.output
                else:
                    output = json.dumps({"error": result.error or "Unknown error"})
            else:
                output = str(result)

            tool_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": tc.get("name", ""),
                "content": output,
            })
        return tool_messages

    async def run(self, user_input: str) -> str:
        text, images = VisionInput.extract_images_from_text(user_input)
        if images and VisionInput.supports_vision(self.config.model):
            msg = VisionInput.build_message_with_images(text or user_input, images)
        else:
            msg = {"role": "user", "content": user_input}
        if self.file_index and isinstance(msg.get("content"), str):
            mentioned_files = []
            words = msg["content"].split()
            for word in words:
                clean = word.strip("\"'`(),;:")
                if "/" in clean or "." in clean:
                    matches = self.file_index.search(clean)
                    if matches:
                        mentioned_files.extend(matches[:3])
            if mentioned_files:
                file_contents = []
                for fp in mentioned_files[:5]:
                    try:
                        full_path = os.path.join(self.file_index.root, fp)
                        if os.path.isfile(full_path) and os.path.getsize(full_path) < 50000:
                            content = open(full_path, "r", errors="ignore").read()
                            file_contents.append(f"[Auto-loaded: {fp}]\n```\n{content[:3000]}\n```")
                    except Exception:
                        pass
                if file_contents:
                    self.conversation_history.append({
                        "role": "system",
                        "content": "Relevant files auto-loaded:\n" + "\n\n".join(file_contents),
                    })
        self.conversation_history.append(msg)
        if self.session_manager and self.session_id:
            await self.session_manager.save_message(self.session_id, {"role": "user", "content": user_input})

        if self.compactor and self.compactor.needs_compaction(self.conversation_history):
            self.conversation_history = await self.compactor.compact(self.conversation_history)

        max_iterations = self.max_turns
        iteration = 0

        if self.token_budget > 0 and self.cost_tracker.total_cost >= self.token_budget:
            return f"[ZER0CODE] Token budget (${self.token_budget:.2f}) exceeded. Current cost: {self.cost_tracker.format_cost()}"

        while iteration < max_iterations:
            iteration += 1

            if self.loop_detector.is_looping():
                loop_info = self.loop_detector.get_loop_info()
                self.conversation_history.append({
                    "role": "system",
                    "content": f"AGENT LOOP DETECTED: {loop_info}\nYou MUST try a completely different approach. Do NOT repeat the same tool calls.",
                })
                self.loop_detector.reset()

            messages = self._get_messages()
            tool_schemas = self._get_tool_schemas()

            response = await self.retry_handler.execute(
                self.provider.chat,
                messages=messages,
                tools=tool_schemas if tool_schemas else None,
            )

            self.cost_tracker.track(
                self.config.model,
                response.usage.get("prompt_tokens", 0),
                response.usage.get("completion_tokens", 0),
            )

            if response.tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                }
                self.conversation_history.append(assistant_msg)

                if self.session_manager and self.session_id:
                    await self.session_manager.save_message(self.session_id, assistant_msg)

                tool_messages = await self._execute_tools_parallel(response.tool_calls)
                for tm in tool_messages:
                    self.conversation_history.append(tm)
                    if self.session_manager and self.session_id:
                        await self.session_manager.save_message(self.session_id, tm)

                if self.reflection and self.reflection.should_trigger_reflection("", False):
                    await self.reflection.periodic_reflection(self.conversation_history)

            else:
                assistant_msg = {"role": "assistant", "content": response.content or ""}
                self.conversation_history.append(assistant_msg)
                if self.session_manager and self.session_id:
                    await self.session_manager.save_message(self.session_id, assistant_msg)
                return response.content or ""

        return "[ZER0CODE] Max iterations (25) reached. Use /compact to reduce context and try again."

    async def run_stream(self, user_input: str) -> AsyncGenerator[str | Dict, None]:
        self.conversation_history.append({"role": "user", "content": user_input})
        if self.reflection and len(self.conversation_history) > 2:
            prev_assistant = ""
            for m in reversed(self.conversation_history[:-1]):
                if m.get("role") == "assistant":
                    prev_assistant = m.get("content", "")
                    break
            try:
                await self.reflection.learn_from_user_correction(user_input, prev_assistant, self.conversation_history)
            except Exception:
                pass
        if self.session_manager and self.session_id:
            await self.session_manager.save_message(self.session_id, {"role": "user", "content": user_input})

        if self.compactor and self.compactor.needs_compaction(self.conversation_history):
            self.conversation_history = await self.compactor.compact(self.conversation_history)
        if self.context_window_usage > 0.8 and self.compactor:
            self.conversation_history = await self.compactor.compact(self.conversation_history)

        max_iterations = self.max_turns
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            if self.loop_detector.is_looping():
                loop_info = self.loop_detector.get_loop_info()
                self.conversation_history.append({
                    "role": "system",
                    "content": f"AGENT LOOP DETECTED: {loop_info}\nYou MUST try a completely different approach.",
                })
                self.loop_detector.reset()

            messages = self._get_messages()
            tool_schemas = self._get_tool_schemas()

            collected_text = []
            collected_tool_calls = []
            stream_usage = {}

            async for chunk in self.provider.stream_chat(messages=messages, tools=tool_schemas if tool_schemas else None):
                if isinstance(chunk, str):
                    collected_text.append(chunk)
                    yield chunk
                elif isinstance(chunk, dict):
                    if chunk.get("type") == "usage":
                        stream_usage = chunk
                    else:
                        collected_tool_calls.append(chunk)

            output_text = "".join(collected_text)
            if stream_usage:
                self.cost_tracker.track(self.config.model, stream_usage.get("prompt_tokens", 0), stream_usage.get("completion_tokens", 0))
            else:
                input_chars = sum(len(str(m.get("content", ""))) for m in messages)
                self.cost_tracker.track(self.config.model, max(input_chars // 4, 1), max(len(output_text) // 4, 1))

            if collected_tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": "".join(collected_text),
                    "tool_calls": collected_tool_calls,
                }
                self.conversation_history.append(assistant_msg)

                for tc in collected_tool_calls:
                    yield {"type": "tool_call", "name": tc.get("name", ""), "arguments": tc.get("arguments", "{}")}

                tool_messages = await self._execute_tools_parallel(collected_tool_calls)
                for tm in tool_messages:
                    self.conversation_history.append(tm)
                    yield {"type": "tool_result", "name": tm.get("name", ""), "content": tm["content"]}

                if self.session_manager and self.session_id:
                    await self.session_manager.save_message(self.session_id, assistant_msg)
                    for tm in tool_messages:
                        await self.session_manager.save_message(self.session_id, tm)
            else:
                full_text = "".join(collected_text)
                assistant_msg = {"role": "assistant", "content": full_text}
                self.conversation_history.append(assistant_msg)
                if self.session_manager and self.session_id:
                    await self.session_manager.save_message(self.session_id, assistant_msg)
                return

        yield "\n[ZER0CODE] Max iterations reached."

    async def load_session(self, session_id: str) -> bool:
        if not self.session_manager:
            return False
        messages = await self.session_manager.load_session(session_id)
        if messages:
            self.conversation_history = messages
            self.session_id = session_id
            return True
        return False

    def reset(self) -> None:
        self.conversation_history.clear()
        self.loop_detector.reset()
        self._start_time = time.time()

    @property
    def session_duration(self) -> float:
        return time.time() - self._start_time

    @property
    def message_count(self) -> int:
        return len([m for m in self.conversation_history if m["role"] in ("user", "assistant")])

    @property
    def total_tokens(self) -> int:
        return self.cost_tracker.total_tokens

    @property
    def total_cost(self) -> str:
        return self.cost_tracker.format_cost()

    @property
    def context_window_usage(self) -> float:
        total_chars = sum(len(str(m.get("content", ""))) for m in self.conversation_history)
        estimated_tokens = total_chars // 4
        return min(estimated_tokens / self._context_max_tokens, 1.0)

    @property
    def context_window_percent(self) -> int:
        return int(self.context_window_usage * 100)
