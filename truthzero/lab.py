"""Bundled vulnerable labs — docker spin-up, attack, teardown.

Labs: crAPI, Juice Shop, VAmPI, DVGA. Legal, safe, zero setup.
Teardown is registered in GLOBAL_CLEANUP BEFORE the container starts
(reverse-order on SIGINT/crash/budget). Fails clean when docker is missing.
"""
from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass


@dataclass
class LabSpec:
    name: str
    image: str
    port: int
    description: str
    health_path: str = "/"


LABS: dict[str, LabSpec] = {
    "crapi": LabSpec("crapi", "owasp/crapi:latest", 8888,
                     "Completely Ridiculous API — BOLA/mass assignment heaven"),
    "juice": LabSpec("juice", "bkimminich/juice-shop:latest", 3000,
                     "OWASP Juice Shop — XSS/SQLi/auth flaws", health_path="/#/"),
    "vampi": LabSpec("vampi", "erev0s/vampi:latest", 5000,
                     "Vulnerable API — JWT/IDOR playground"),
    "dvga": LabSpec("dvga", "dolevf/graphql-cop:alpine", 5013,
                    "Damn Vulnerable GraphQL API — injection/BOLA"),
}


class LabManager:
    def __init__(self, scope_checker=None):
        self._scope_checker = scope_checker
        self._running: dict[str, str] = {}  # lab -> container id

    @staticmethod
    def docker_ok() -> bool:
        return bool(shutil.which("docker"))

    def list_labs(self) -> list[LabSpec]:
        return list(LABS.values())

    async def up(self, lab: str) -> str:
        """Start lab container. Returns base URL. Registers teardown first."""
        spec = LABS.get(lab)
        if not spec:
            raise ValueError(f"Unknown lab: {lab}. Available: {sorted(LABS)}")
        if not self.docker_ok():
            raise FileNotFoundError("docker not installed — cannot spin up labs")
        from truthzero.cleanup import GLOBAL_CLEANUP
        GLOBAL_CLEANUP.register(f"lab-{lab}-teardown",
                                lambda: self._teardown_sync(lab))
        proc = await asyncio.create_subprocess_exec(
            "docker", "run", "-d", "--rm", "-p", f"{spec.port}:{spec.port}",
            "--name", f"truthzero-{lab}", spec.image,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"docker run failed: {(stderr or b'').decode()[:500]}")
        cid = (stdout or b"").decode().strip()
        self._running[lab] = cid
        await asyncio.sleep(3)  # let the app boot
        return f"http://127.0.0.1:{spec.port}"

    async def down(self, lab: str) -> bool:
        cid = self._running.get(lab, f"truthzero-{lab}")
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", cid,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await asyncio.wait_for(proc.communicate(), timeout=60)
            self._running.pop(lab, None)
            return True
        except Exception:
            return False

    def _teardown_sync(self, lab: str) -> None:
        import subprocess as _sp
        cid = self._running.get(lab, f"truthzero-{lab}")
        try:
            _sp.run(["docker", "rm", "-f", cid], timeout=60,
                    capture_output=True)
        except Exception:
            pass
        self._running.pop(lab, None)
