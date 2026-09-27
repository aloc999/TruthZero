"""OWASP ZAP adapter — baseline + API scan via zap-cli / Docker.

Prefers `zap-cli` if installed, else the official ZAP Docker image
(ghcr.io/zaproxy/zap-stable). Baseline = spider + passive scan only
(safe for CI); api-scan hits an OpenAPI target. Fails with install hint.
"""
from __future__ import annotations

import asyncio
import shutil

from zer0code.tools.base import BaseTool, ToolResult


class ZapTool(BaseTool):
    name = "zap_scan"
    description = "OWASP ZAP baseline (spider+passive) or OpenAPI scan. Safe CI defaults."
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target base URL"},
            "mode": {"type": "string", "enum": ["baseline", "api-scan"], "default": "baseline"},
            "api_spec": {"type": "string", "description": "OpenAPI spec URL (api-scan mode)"},
            "timeout": {"type": "integer", "default": 600},
        },
        "required": ["target"],
    }

    async def execute(self, target: str = "", mode: str = "baseline",
                      api_spec: str = "", timeout: int = 600, **kwargs) -> ToolResult:
        if not target:
            return ToolResult(output="", success=False, error="target required")
        if mode == "api-scan" and not api_spec:
            return ToolResult(output="", success=False,
                              error="api-scan needs api_spec URL")
        if shutil.which("zap-cli"):
            cmd = (["zap-cli", "quick-scan", "--self-contained",
                     "--spider", "--recursive", target]
                   if mode == "baseline"
                   else ["zap-cli", "openapi", api_spec])
            runner = self._run
        elif shutil.which("docker"):
            if mode == "baseline":
                cmd = ["docker", "run", "--rm", "-t",
                       "ghcr.io/zaproxy/zap-stable:latest",
                       "zap-baseline.py", "-t", target]
            else:
                cmd = ["docker", "run", "--rm", "-t",
                       "ghcr.io/zaproxy/zap-stable:latest",
                       "zap-api-scan.py", "-t", api_spec, "-f", "openapi"]
            runner = self._run
        else:
            return ToolResult(
                output="", success=False,
                error="Neither zap-cli nor docker found. Install: pip install zap-cli, or docker pull ghcr.io/zaproxy/zap-stable")
        return await runner(cmd, timeout)

    async def _run(self, cmd: list[str], timeout: int) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = (stdout or b"").decode(errors="replace")
            err = (stderr or b"").decode(errors="replace")
            # zap-baseline exits non-zero on WARN/FAIL by design — still useful output
            text = (out + "\n" + err)[-8000:]
            if "WARN" in text or "FAIL" in text:
                text = "CANDIDATE: ZAP baseline flagged issues (see WARN/FAIL lines)\n" + text
            return ToolResult(output=text, success=True)
        except asyncio.TimeoutError:
            return ToolResult(output="", success=False, error=f"ZAP timed out ({timeout}s)")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
