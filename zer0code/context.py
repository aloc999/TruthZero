import asyncio
import os
import json
from pathlib import Path
from typing import Optional


PROJECT_CONTEXT_FILES = [
    ".zer0code.md",
    ".zer0code",
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
]


class ProjectContext:
    def __init__(self):
        self.project_root: Optional[str] = None
        self.instructions: str = ""
        self.detected_stack: dict = {}

    def detect_project_root(self, start_path: str = ".") -> Optional[str]:
        current = Path(start_path).resolve()
        for _ in range(10):
            if (current / ".git").exists():
                self.project_root = str(current)
                return str(current)
            for ctx_file in PROJECT_CONTEXT_FILES:
                if (current / ctx_file).exists():
                    self.project_root = str(current)
                    return str(current)
            parent = current.parent
            if parent == current:
                break
            current = parent
        self.project_root = str(Path(start_path).resolve())
        return self.project_root

    def load_instructions(self) -> str:
        if not self.project_root:
            self.detect_project_root()

        root = Path(self.project_root)
        for ctx_file in PROJECT_CONTEXT_FILES:
            filepath = root / ctx_file
            if filepath.exists() and filepath.is_file():
                try:
                    content = filepath.read_text(encoding="utf-8")
                    self.instructions = content
                    return content
                except Exception:
                    continue
        return ""

    def detect_tech_stack(self) -> dict:
        if not self.project_root:
            return {}

        root = Path(self.project_root)
        stack = {}

        indicators = {
            "package.json": "node",
            "pyproject.toml": "python",
            "setup.py": "python",
            "requirements.txt": "python",
            "Cargo.toml": "rust",
            "go.mod": "go",
            "pom.xml": "java",
            "build.gradle": "java",
            "Gemfile": "ruby",
            "composer.json": "php",
            "Dockerfile": "docker",
            "docker-compose.yml": "docker",
            ".terraform": "terraform",
            "Makefile": "make",
        }

        for filename, tech in indicators.items():
            if (root / filename).exists():
                stack[tech] = filename

        lint_configs = {
            ".eslintrc.json": "eslint",
            ".eslintrc.js": "eslint",
            "ruff.toml": "ruff",
            ".flake8": "flake8",
            "tsconfig.json": "typescript",
        }

        for filename, tool in lint_configs.items():
            if (root / filename).exists():
                stack[f"lint_{tool}"] = filename

        self.detected_stack = stack
        return stack

    def get_context_prompt(self) -> str:
        parts = []
        if self.instructions:
            parts.append(f"PROJECT INSTRUCTIONS:\n{self.instructions}")
        if self.detected_stack:
            tech_list = ", ".join(self.detected_stack.keys())
            parts.append(f"DETECTED TECH STACK: {tech_list}")
        if self.project_root:
            parts.append(f"PROJECT ROOT: {self.project_root}")
        return "\n\n".join(parts)


class ContextCompactor:
    MAX_MESSAGES_BEFORE_COMPACT = 40
    KEEP_RECENT = 10

    def __init__(self, provider=None):
        self._provider = provider

    def needs_compaction(self, messages: list[dict]) -> bool:
        non_system = [m for m in messages if m["role"] != "system"]
        return len(non_system) > self.MAX_MESSAGES_BEFORE_COMPACT

    async def compact(self, messages: list[dict]) -> list[dict]:
        non_system = [m for m in messages if m["role"] != "system"]
        system = [m for m in messages if m["role"] == "system"]

        if len(non_system) <= self.MAX_MESSAGES_BEFORE_COMPACT:
            return messages

        old_messages = non_system[:-self.KEEP_RECENT]
        recent_messages = non_system[-self.KEEP_RECENT:]

        summary = self._generate_summary(old_messages)

        compacted = system + [
            {"role": "system", "content": f"CONVERSATION SUMMARY (compacted):\n{summary}"}
        ] + recent_messages

        return compacted

    def _generate_summary(self, messages: list[dict]) -> str:
        parts = []
        parts.append(f"Previous conversation had {len(messages)} messages.")

        user_queries = []
        tool_calls = []
        key_findings = []

        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue

            if msg["role"] == "user":
                if len(content) > 200:
                    content = content[:200] + "..."
                user_queries.append(content)
            elif msg["role"] == "tool":
                name = msg.get("name", "unknown")
                tool_calls.append(name)
                if "error" in content.lower() or "found" in content.lower():
                    key_findings.append(f"{name}: {content[:150]}")

        if user_queries:
            parts.append("User asked about: " + "; ".join(user_queries[:5]))
        if tool_calls:
            unique_tools = list(dict.fromkeys(tool_calls))
            parts.append(f"Tools used: {', '.join(unique_tools)}")
        if key_findings:
            parts.append("Key findings: " + "; ".join(key_findings[:5]))

        return "\n".join(parts)

    async def compact_with_llm(self, messages: list[dict]) -> list[dict]:
        if not self._provider:
            return await self.compact(messages)

        non_system = [m for m in messages if m["role"] != "system"]
        system = [m for m in messages if m["role"] == "system"]

        if len(non_system) <= self.MAX_MESSAGES_BEFORE_COMPACT:
            return messages

        old_messages = non_system[:-self.KEEP_RECENT]
        recent_messages = non_system[-self.KEEP_RECENT:]

        summary_prompt = [
            {"role": "system", "content": "Summarize this conversation concisely. Include: what was discussed, what tools were used, what findings were made, and any important context for continuing the conversation. Be brief but complete."},
            {"role": "user", "content": self._format_messages_for_summary(old_messages)},
        ]

        try:
            response = await self._provider.chat(messages=summary_prompt)
            summary = response.content
        except Exception:
            summary = self._generate_summary(old_messages)

        compacted = system + [
            {"role": "system", "content": f"CONVERSATION SUMMARY (compacted from {len(old_messages)} messages):\n{summary}"}
        ] + recent_messages

        return compacted

    def _format_messages_for_summary(self, messages: list[dict]) -> str:
        parts = []
        for msg in messages[:30]:
            role = msg["role"]
            content = msg.get("content", "")
            if not isinstance(content, str):
                content = str(content)
            if len(content) > 300:
                content = content[:300] + "..."
            parts.append(f"[{role}]: {content}")
        return "\n".join(parts)
