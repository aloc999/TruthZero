import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class HookResult:
    proceed: bool = True
    message: str = ""
    modified_args: dict | None = None


@dataclass
class Hook:
    name: str
    event: str
    callback: Callable
    priority: int = 0


class HookManager:
    def __init__(self):
        self._hooks: dict[str, list[Hook]] = {}

    def register(self, event: str, name: str, callback: Callable, priority: int = 0):
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(Hook(name=name, event=event, callback=callback, priority=priority))
        self._hooks[event].sort(key=lambda h: h.priority, reverse=True)

    def unregister(self, event: str, name: str):
        if event in self._hooks:
            self._hooks[event] = [h for h in self._hooks[event] if h.name != name]

    async def trigger(self, event: str, **kwargs) -> list[HookResult]:
        results = []
        for hook in self._hooks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(hook.callback):
                    result = await hook.callback(**kwargs)
                else:
                    result = hook.callback(**kwargs)
                if isinstance(result, HookResult):
                    results.append(result)
                    if not result.proceed:
                        break
                else:
                    results.append(HookResult(proceed=True))
            except Exception as e:
                results.append(HookResult(proceed=True, message=f"Hook {hook.name} error: {e}"))
        return results

    def list_hooks(self) -> dict[str, list[str]]:
        return {event: [h.name for h in hooks] for event, hooks in self._hooks.items()}


class AutoLintHook:
    LINT_COMMANDS = {
        ".py": ["ruff check --fix {file}", "ruff format {file}"],
        ".js": ["npx eslint --fix {file}"],
        ".ts": ["npx eslint --fix {file}", "npx tsc --noEmit"],
        ".tsx": ["npx eslint --fix {file}", "npx tsc --noEmit"],
        ".rs": ["cargo clippy"],
        ".go": ["gofmt -w {file}"],
    }

    @staticmethod
    async def on_file_write(file_path: str = "", **kwargs) -> HookResult:
        if not file_path:
            return HookResult(proceed=True)

        ext = os.path.splitext(file_path)[1]
        commands = AutoLintHook.LINT_COMMANDS.get(ext, [])

        results = []
        for cmd_template in commands:
            cmd = cmd_template.format(file=file_path)
            try:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=os.path.dirname(file_path) or ".",
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
                if proc.returncode != 0:
                    output = (stderr or stdout or b"").decode("utf-8", errors="replace").strip()
                    results.append(f"Lint ({cmd.split()[0]}): {output[:500]}")
            except FileNotFoundError:
                pass
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

        if results:
            return HookResult(proceed=True, message="\n".join(results))
        return HookResult(proceed=True)


class AutoLSPHook:
    @staticmethod
    async def on_file_write(file_path: str = "", **kwargs) -> HookResult:
        if not file_path:
            return HookResult(proceed=True)

        try:
            from zer0code.lsp import LSPClient
            diagnostics = await LSPClient.get_diagnostics_simple(file_path)
            if diagnostics:
                messages = []
                for d in diagnostics[:5]:
                    sev = d.get("severity", "info")
                    msg = d.get("message", "")
                    line = d.get("line", "?")
                    messages.append(f"[{sev}] line {line}: {msg}")
                if messages:
                    return HookResult(proceed=True, message="LSP: " + "; ".join(messages))
        except Exception:
            pass

        return HookResult(proceed=True)
