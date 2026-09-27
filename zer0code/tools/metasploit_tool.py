"""Metasploit adapter — msfconsole resource-script runner.

Executes a generated .rc resource script via msfconsole -r with a strict
allowlist of safe auxiliary/scanner modules + `check` only. Exploit
modules with payloads are REFUSED — the agent proves via check/scanner
output, never fires payloads autonomously. Fails with install hint when
msfconsole is missing.
"""
from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from pathlib import Path

from zer0code.tools.base import BaseTool, ToolResult

# Allowlist: scanners + check-capable auxiliaries only. No exploit/* with payloads.
ALLOWED_MODULE_RE = re.compile(
    r"^(auxiliary/scanner/|auxiliary/gather/|exploit/.*/check$)"
)


class MetasploitTool(BaseTool):
    name = "msf_run"
    description = (
        "Run Metasploit scanner/check modules via resource script "
        "(allowlist: auxiliary/scanner, gather, check-only)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "module": {"type": "string", "description": "Module path, e.g. auxiliary/scanner/http/http_version"},
            "rhosts": {"type": "string", "description": "RHOSTS value (scope-checked by agent)"},
            "rport": {"type": "integer", "description": "RPORT value"},
            "options": {"type": "string", "description": "Extra KEY=VALUE lines, one per line"},
        },
        "required": ["module", "rhosts"],
    }

    async def execute(self, module: str = "", rhosts: str = "", rport: int = 0,
                      options: str = "", **kwargs) -> ToolResult:
        if not module or not rhosts:
            return ToolResult(output="", success=False, error="module + rhosts required")
        if not ALLOWED_MODULE_RE.match(module):
            return ToolResult(
                output="", success=False,
                error=f"Module not in allowlist (scanner/gather/check-only): {module}")
        if not shutil.which("msfconsole"):
            return ToolResult(output="", success=False,
                              error="msfconsole not installed. Install: apt install metasploit-framework")
        lines = [f"use {module}", f"set RHOSTS {rhosts}"]
        if rport:
            lines.append(f"set RPORT {rport}")
        for line in (options or "").splitlines():
            line = line.strip()
            if not line or line.lower().startswith(("set payload", "exploit", "run -j")):
                continue
            if re.match(r"^set\s+\w+\s+\S+", line, re.IGNORECASE):
                lines.append(line)
        lines += ["check", "exit"]
        rc = Path(tempfile.mkstemp(suffix=".rc")[1])
        rc.write_text("\n".join(lines) + "\n")
        try:
            proc = await asyncio.create_subprocess_exec(
                "msfconsole", "-q", "-r", str(rc),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            out = (stdout or b"").decode(errors="replace")
            tail = out[-6000:]
            if re.search(r"vulnerable|appears|The target is", tail, re.IGNORECASE):
                tail = "CANDIDATE: msf check reports possible vulnerability\n" + tail
            return ToolResult(output=tail, success=proc.returncode == 0)
        except asyncio.TimeoutError:
            return ToolResult(output="", success=False, error="msfconsole timed out (600s)")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
        finally:
            try:
                rc.unlink()
            except Exception:
                pass
