import asyncio
import json
import os
from truthzero.tools.base import BaseTool, ToolResult


class DepsScanTool(BaseTool):
    name = "deps_scan"
    description = "Scan project dependencies for known CVEs. Supports Python (pip-audit), Node (npm audit), and Ruby (bundle audit)."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project directory path", "default": "."},
            "ecosystem": {"type": "string", "enum": ["auto", "python", "node", "ruby", "go"], "default": "auto"},
        },
        "required": [],
    }

    async def execute(self, path: str = ".", ecosystem: str = "auto", **kwargs) -> ToolResult:
        results = []
        detected = ecosystem

        if detected == "auto":
            if os.path.exists(os.path.join(path, "requirements.txt")) or os.path.exists(os.path.join(path, "pyproject.toml")):
                detected = "python"
            elif os.path.exists(os.path.join(path, "package.json")):
                detected = "node"
            elif os.path.exists(os.path.join(path, "Gemfile")):
                detected = "ruby"
            elif os.path.exists(os.path.join(path, "go.mod")):
                detected = "go"
            else:
                return ToolResult(output="No supported dependency file found (requirements.txt, package.json, Gemfile, go.mod)", success=True)

        if detected == "python":
            results.append(await self._scan_python(path))
        elif detected == "node":
            results.append(await self._scan_node(path))
        elif detected == "ruby":
            results.append(await self._scan_ruby(path))
        elif detected == "go":
            results.append(await self._scan_go(path))

        output = "\n".join(results)
        return ToolResult(output=output, success=True)

    async def _run_cmd(self, cmd: str, cwd: str = ".") -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            return (stdout or stderr or b"").decode("utf-8", errors="replace")
        except FileNotFoundError:
            return f"Command not found: {cmd.split()[0]}"
        except asyncio.TimeoutError:
            return "Scan timed out"
        except Exception as e:
            return str(e)

    async def _scan_python(self, path: str) -> str:
        for cmd in ["pip-audit", "safety check --json", "pip install pip-audit && pip-audit"]:
            result = await self._run_cmd(cmd, path)
            if "not found" not in result.lower():
                return f"[Python Dependency Scan]\n{result}"
        return "[Python] Install pip-audit: pip install pip-audit"

    async def _scan_node(self, path: str) -> str:
        result = await self._run_cmd("npm audit --json", path)
        if "not found" not in result.lower():
            try:
                data = json.loads(result)
                vulns = data.get("vulnerabilities", {})
                if not vulns:
                    return "[Node] No vulnerabilities found."
                lines = [f"[Node Dependency Scan] {len(vulns)} vulnerable packages:"]
                for pkg, info in list(vulns.items())[:20]:
                    severity = info.get("severity", "unknown")
                    via = ", ".join(v if isinstance(v, str) else v.get("name", "") for v in info.get("via", [])[:3])
                    lines.append(f"  {pkg} [{severity}] via: {via}")
                return "\n".join(lines)
            except json.JSONDecodeError:
                return f"[Node Dependency Scan]\n{result[:2000]}"
        return "[Node] npm not found"

    async def _scan_ruby(self, path: str) -> str:
        return await self._run_cmd("bundle audit check", path)

    async def _scan_go(self, path: str) -> str:
        return await self._run_cmd("govulncheck ./...", path)
