"""Native security toolchain — ProjectDiscovery + nmap, scope-validated.

Mirrors Pentest-Swarm-AI's stable toolchain:
subfinder · httpx · nuclei · naabu · katana · dnsx · gau · nmap
Each tool runs as subprocess with --scope pre-check (defence layer 1;
the scheduler/scope manager is layer 2).
"""
from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass


@dataclass
class ToolSpec:
    name: str
    binary: str
    install_hint: str
    description: str


TOOLCHAIN: list[ToolSpec] = [
    ToolSpec("subfinder", "subfinder", "go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest", "Subdomain enumeration"),
    ToolSpec("httpx", "httpx", "go install github.com/projectdiscovery/httpx/cmd/httpx@latest", "Alive probe + tech fingerprint"),
    ToolSpec("nuclei", "nuclei", "go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest", "Vulnerability scanning"),
    ToolSpec("naabu", "naabu", "go install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest", "Port scanning"),
    ToolSpec("katana", "katana", "go install github.com/projectdiscovery/katana/cmd/katana@latest", "Crawling"),
    ToolSpec("dnsx", "dnsx", "go install github.com/projectdiscovery/dnsx/cmd/dnsx@latest", "DNS toolkit"),
    ToolSpec("gau", "gau", "go install github.com/lc/gau/v2/cmd/gau@latest", "URL discovery (wayback)"),
    ToolSpec("nmap", "nmap", "apt install nmap", "Port/service scan (XML parsed)"),
]


class ToolchainManager:
    def __init__(self, scope_checker=None):
        self._scope_checker = scope_checker

    def status(self) -> list[dict]:
        out = []
        for t in TOOLCHAIN:
            path = shutil.which(t.binary)
            out.append({"name": t.name, "binary": t.binary,
                        "installed": bool(path), "path": path or "",
                        "hint": t.install_hint, "description": t.description})
        return out

    def missing(self) -> list[ToolSpec]:
        return [t for t in TOOLCHAIN if not shutil.which(t.binary)]

    def _check_scope(self, target: str) -> None:
        if self._scope_checker and not self._scope_checker(target):
            raise PermissionError(f"Target out of scope: {target}")

    async def run(self, binary: str, args: list[str], target: str = "",
                  timeout: float = 300.0) -> tuple[str, str, int]:
        """Run a toolchain binary. Returns (stdout, stderr, returncode)."""
        if target:
            self._check_scope(target)
        if not shutil.which(binary):
            raise FileNotFoundError(f"{binary} not installed")
        proc = await asyncio.create_subprocess_exec(
            binary, *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"{binary} timed out after {timeout}s")
        return (stdout.decode(errors="replace"), stderr.decode(errors="replace"),
                proc.returncode or 0)
