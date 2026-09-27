import re
from pathlib import Path

from truthzero.tools.base import BaseTool, ToolResult


class SearchReplaceTool(BaseTool):
    name = "search_replace"
    description = "Search and replace text across multiple files in a project. Supports regex."
    parameters = {
        "type": "object",
        "properties": {
            "search": {"type": "string", "description": "Text or regex pattern to find"},
            "replace": {"type": "string", "description": "Replacement text"},
            "path": {"type": "string", "description": "Directory to search in", "default": "."},
            "include": {"type": "string", "description": "File glob pattern (e.g., '*.py')"},
            "regex": {"type": "boolean", "description": "Treat search as regex", "default": False},
            "dry_run": {"type": "boolean", "description": "Preview changes without applying", "default": False},
        },
        "required": ["search", "replace"],
    }

    async def execute(self, search: str = "", replace: str = "", path: str = ".", include: str = "", regex: bool = False, dry_run: bool = False, **kwargs) -> ToolResult:
        try:
            root = Path(path).resolve()
            if not root.exists():
                return ToolResult(output="", success=False, error=f"Path not found: {path}")

            if include:
                files = list(root.rglob(include))
            else:
                files = [f for f in root.rglob("*") if f.is_file() and not any(p in str(f) for p in [".git", "__pycache__", "node_modules", ".venv"])]

            results = []
            total_replacements = 0

            for filepath in files:
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                if regex:
                    pattern = re.compile(search)
                    matches = pattern.findall(content)
                    if not matches:
                        continue
                    new_content = pattern.sub(replace, content)
                    count = len(matches)
                else:
                    count = content.count(search)
                    if count == 0:
                        continue
                    new_content = content.replace(search, replace)

                total_replacements += count
                rel = filepath.relative_to(root)
                results.append(f"  {rel}: {count} replacement(s)")

                if not dry_run:
                    filepath.write_text(new_content, encoding="utf-8")

            if not results:
                return ToolResult(output=f"No matches found for '{search}'", success=True)

            prefix = "[DRY RUN] " if dry_run else ""
            header = f"{prefix}{total_replacements} replacement(s) across {len(results)} file(s):\n"
            return ToolResult(output=header + "\n".join(results), success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
