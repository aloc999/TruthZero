import fnmatch
import os
import re
from pathlib import Path

from zer0code.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read a file and return its contents with line numbers"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to read",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "default": 2000,
            },
        },
        "required": ["file_path"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", 2000)

        if not file_path:
            return ToolResult(output="", success=False, error="No file path provided")

        path = Path(file_path)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {file_path}")

        if path.is_dir():
            try:
                entries = sorted(path.iterdir())
                lines = []
                for entry in entries:
                    name = entry.name + ("/" if entry.is_dir() else "")
                    lines.append(name)
                return ToolResult(output="\n".join(lines), success=True)
            except PermissionError:
                return ToolResult(output="", success=False, error=f"Permission denied: {file_path}")

        try:
            content = path.read_bytes()
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = content.decode("latin-1")
                except Exception:
                    return ToolResult(
                        output=f"Binary file: {len(content)} bytes", success=True
                    )

            lines = text.splitlines(keepends=True)
            start = max(0, (offset or 1) - 1)
            end = start + (limit or 2000)
            selected = lines[start:end]

            numbered = []
            for i, line in enumerate(selected, start=start + 1):
                numbered.append(f"{i}: {line.rstrip()}")

            output = "\n".join(numbered)
            if end < len(lines):
                output += f"\n\n... ({len(lines) - end} more lines)"

            return ToolResult(output=output, success=True)

        except PermissionError:
            return ToolResult(output="", success=False, error=f"Permission denied: {file_path}")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file, creating parent directories if needed"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")

        if not file_path:
            return ToolResult(output="", success=False, error="No file path provided")

        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                output=f"Wrote {len(content)} bytes to {file_path}", success=True
            )
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))


class EditFileTool(BaseTool):
    name = "edit_file"
    description = "Edit a file by replacing a string with another string"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The text to find and replace",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences",
                "default": False,
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

        if not file_path:
            return ToolResult(output="", success=False, error="No file path provided")
        if not old_string:
            return ToolResult(output="", success=False, error="No old_string provided")
        if old_string == new_string:
            return ToolResult(output="", success=False, error="old_string and new_string are identical")

        path = Path(file_path)
        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {file_path}")

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

        count = content.count(old_string)
        if count == 0:
            return ToolResult(
                output="", success=False, error="oldString not found in content"
            )

        if count > 1 and not replace_all:
            return ToolResult(
                output="",
                success=False,
                error="Found multiple matches for oldString. Provide more surrounding lines in oldString to identify the correct match.",
            )

        if replace_all:
            new_content = content.replace(old_string, new_string)
        else:
            new_content = content.replace(old_string, new_string, 1)

        try:
            path.write_text(new_content, encoding="utf-8")
            return ToolResult(
                output=f"Replaced {count if replace_all else 1} occurrence(s) in {file_path}",
                success=True,
            )
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))


class GlobTool(BaseTool):
    name = "glob"
    description = "Find files matching a glob pattern"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files against",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")

        if not pattern:
            return ToolResult(output="", success=False, error="No pattern provided")

        try:
            base = Path(search_path).resolve()
            if not base.exists():
                return ToolResult(
                    output="", success=False, error=f"Path does not exist: {search_path}"
                )

            matches = sorted(str(p) for p in base.glob(pattern) if not str(p.name).startswith("."))
            if not matches:
                return ToolResult(output="No matches found", success=True)

            return ToolResult(output="\n".join(matches), success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))


class GrepTool(BaseTool):
    name = "grep"
    description = "Search file contents using a regular expression"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in",
            },
            "include": {
                "type": "string",
                "description": "File pattern to include (e.g. '*.py')",
            },
        },
        "required": ["pattern"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        include = kwargs.get("include", None)

        if not pattern:
            return ToolResult(output="", success=False, error="No pattern provided")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(output="", success=False, error=f"Invalid regex: {e}")

        base = Path(search_path).resolve()
        if not base.exists():
            return ToolResult(
                output="", success=False, error=f"Path does not exist: {search_path}"
            )

        results = []
        max_results = 1000

        try:
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for filename in sorted(files):
                    if filename.startswith("."):
                        continue
                    if include and not fnmatch.fnmatch(filename, include):
                        continue

                    filepath = Path(root) / filename
                    try:
                        text = filepath.read_text(encoding="utf-8", errors="ignore")
                    except (PermissionError, OSError):
                        continue

                    for lineno, line in enumerate(text.splitlines(), 1):
                        if regex.search(line):
                            results.append(f"{filepath}:{lineno}:{line.rstrip()}")
                            if len(results) >= max_results:
                                results.append(f"\n... truncated at {max_results} results")
                                return ToolResult(output="\n".join(results), success=True)

        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

        if not results:
            return ToolResult(output="No matches found", success=True)

        return ToolResult(output="\n".join(results), success=True)
