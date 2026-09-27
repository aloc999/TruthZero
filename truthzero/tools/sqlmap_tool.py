"""sqlmap adapter — safe SQL injection testing.

Wraps the sqlmap binary with scope-safe defaults: read-only fingerprint
actions first (dbs/tables only on explicit action). Never runs --os-shell
or destructive flags. Fails with install hint when sqlmap is missing.
"""
from __future__ import annotations

import asyncio
import shutil

from truthzero.tools.base import BaseTool, ToolResult

SAFE_LEVEL = 2
SAFE_RISK = 1


class SqlmapTool(BaseTool):
    name = "sqlmap_scan"
    description = (
        "Test URL for SQL injection with sqlmap (safe defaults: "
        "level=2 risk=1, no OS shell, batch mode)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL with parameter"},
            "action": {"type": "string",
                       "enum": ["fingerprint", "dbs", "tables", "dump-check"],
                       "default": "fingerprint"},
            "db": {"type": "string", "description": "Database for tables action"},
            "cookie": {"type": "string", "description": "Session cookie for auth"},
            "extra_args": {"type": "string", "description": "Extra safe args (no --os-shell etc.)"},
        },
        "required": ["url"],
    }

    BLOCKED = ("--os-shell", "--os-cmd", "--os-pwn", "--priv-esc",
               "--sql-shell", "--eval", "--drop-set-cookie", "--flush-session",
               "--purge", "--drop-table", "--delete")

    async def execute(self, url: str = "", action: str = "fingerprint",
                      db: str = "", cookie: str = "", extra_args: str = "",
                      **kwargs) -> ToolResult:
        if not url:
            return ToolResult(output="", success=False, error="url required")
        if not shutil.which("sqlmap"):
            return ToolResult(output="", success=False,
                              error="sqlmap not installed. Install: apt install sqlmap")
        for blocked in self.BLOCKED:
            if blocked in (extra_args or ""):
                return ToolResult(output="", success=False,
                                  error=f"Blocked destructive flag: {blocked}")
        cmd = ["sqlmap", "-u", url, "--batch",
               f"--level={SAFE_LEVEL}", f"--risk={SAFE_RISK}",
               "--smart", "--answer", "crack=N,dict=N"]
        if action == "fingerprint":
            cmd += ["--fingerprint", "--banner"]
        elif action == "dbs":
            cmd += ["--dbs"]
        elif action == "tables":
            if not db:
                return ToolResult(output="", success=False,
                                  error="tables action needs db")
            cmd += ["-D", db, "--tables"]
        elif action == "dump-check":
            cmd += ["--dbs", "--stop", "1"]
        else:
            return ToolResult(output="", success=False, error=f"Unknown action: {action}")
        if cookie:
            cmd += ["--cookie", cookie]
        if extra_args:
            cmd += extra_args.split()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            out = (stdout or b"").decode(errors="replace")
            if "is vulnerable" in out or "injectable" in out:
                out = "CONFIRMED: sqlmap reports injectable parameter\n" + out[-4000:]
            return ToolResult(output=out[-6000:] or (stderr or b"").decode(errors="replace")[-1000:],
                              success=proc.returncode == 0)
        except asyncio.TimeoutError:
            return ToolResult(output="", success=False, error="sqlmap timed out (600s)")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
