import asyncio
from pathlib import Path

from truthzero.tools.base import BaseTool, ToolResult


class NucleiManagerTool(BaseTool):
    name = "nuclei_manage"
    description = "Manage nuclei templates — update, list, search, and get info on available templates."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["update", "list", "search", "info", "count"], "default": "list"},
            "query": {"type": "string", "description": "Search query or template name"},
            "severity": {"type": "string", "enum": ["info", "low", "medium", "high", "critical", ""], "default": ""},
            "tags": {"type": "string", "description": "Filter by tags (comma-separated)"},
        },
        "required": ["action"],
    }

    async def execute(self, action: str = "list", query: str = "", severity: str = "", tags: str = "", **kwargs) -> ToolResult:
        if action == "update":
            return await self._update()
        elif action == "list":
            return await self._list(severity, tags)
        elif action == "search":
            return await self._search(query, severity)
        elif action == "info":
            return await self._info(query)
        elif action == "count":
            return await self._count()
        return ToolResult(output="", success=False, error=f"Unknown action: {action}")

    async def _run_cmd(self, cmd: str, timeout: int = 60) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = (stdout or b"").decode("utf-8", errors="replace")
            if not output:
                output = (stderr or b"").decode("utf-8", errors="replace")
            return proc.returncode == 0, output
        except FileNotFoundError:
            return False, "nuclei not installed. Install: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
        except asyncio.TimeoutError:
            return False, "Command timed out"

    async def _update(self) -> ToolResult:
        ok, output = await self._run_cmd("nuclei -update-templates", timeout=120)
        if ok:
            return ToolResult(output=f"Templates updated.\n{output}", success=True)
        return ToolResult(output="", success=False, error=output)

    async def _list(self, severity: str, tags: str) -> ToolResult:
        cmd = "nuclei -tl"
        if severity:
            cmd += f" -severity {severity}"
        if tags:
            cmd += f" -tags {tags}"
        ok, output = await self._run_cmd(cmd)
        if ok:
            lines = output.strip().split("\n")
            return ToolResult(output=f"{len(lines)} templates:\n" + "\n".join(lines[:100]), success=True)
        return ToolResult(output="", success=False, error=output)

    async def _search(self, query: str, severity: str) -> ToolResult:
        if not query:
            return ToolResult(output="", success=False, error="Provide a search query")
        cmd = "nuclei -tl"
        if severity:
            cmd += f" -severity {severity}"
        ok, output = await self._run_cmd(cmd)
        if ok:
            lines = [line for line in output.strip().split("\n") if query.lower() in line.lower()]
            if lines:
                return ToolResult(output=f"{len(lines)} matching templates:\n" + "\n".join(lines[:50]), success=True)
            return ToolResult(output=f"No templates matching '{query}'", success=True)
        return ToolResult(output="", success=False, error=output)

    async def _info(self, template: str) -> ToolResult:
        if not template:
            return ToolResult(output="", success=False, error="Provide template name")
        templates_dir = Path.home() / "nuclei-templates"
        matches = list(templates_dir.rglob(f"*{template}*")) if templates_dir.exists() else []
        if matches:
            info = []
            for m in matches[:5]:
                info.append(f"  {m.relative_to(templates_dir)}")
                try:
                    content = m.read_text()[:500]
                    info.append(f"  {content}")
                except Exception:
                    pass
            return ToolResult(output="\n".join(info), success=True)
        return ToolResult(output=f"Template '{template}' not found", success=True)

    async def _count(self) -> ToolResult:
        ok, output = await self._run_cmd("nuclei -tl | wc -l")
        if ok:
            return ToolResult(output=f"Total templates: {output.strip()}", success=True)
        return ToolResult(output="", success=False, error=output)
