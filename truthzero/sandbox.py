import asyncio
import json
import os
import shutil
from typing import Optional


SANDBOX_IMAGE = "kalilinux/kali-rolling"
CONTAINER_NAME = "truthzero-sandbox"

SETUP_COMMANDS = [
    "apt-get update -qq",
    "apt-get install -y -qq nmap ffuf nuclei subfinder httpx-toolkit whois dnsutils netcat-openbsd curl wget git python3 python3-pip gobuster wfuzz sqlmap nikto dirb seclists wordlists 2>/dev/null || true",
]


class DockerSandbox:
    def __init__(self, image: str = SANDBOX_IMAGE, container_name: str = CONTAINER_NAME, memory_limit: str = "4g", workspace: str = ""):
        self.image = image
        self.container_name = container_name
        self.memory_limit = memory_limit
        self.workspace = workspace or os.path.join(os.getcwd(), "workspace")
        self._running = False

    @property
    def is_docker_available(self) -> bool:
        return shutil.which("docker") is not None

    async def _run(self, cmd: str, timeout: int = 300) -> tuple[int, str]:
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = (stdout or b"").decode("utf-8", errors="replace")
            if not output:
                output = (stderr or b"").decode("utf-8", errors="replace")
            return proc.returncode or 0, output
        except asyncio.TimeoutError:
            return 1, "Command timed out"
        except Exception as e:
            return 1, str(e)

    async def start(self) -> tuple[bool, str]:
        if not self.is_docker_available:
            return False, "Docker not installed. Install: https://docs.docker.com/get-docker/"

        os.makedirs(self.workspace, exist_ok=True)

        code, output = await self._run(f"docker inspect {self.container_name} 2>/dev/null")
        if code == 0:
            state = json.loads(output)[0].get("State", {})
            if state.get("Running"):
                self._running = True
                return True, f"Sandbox already running: {self.container_name}"
            await self._run(f"docker rm -f {self.container_name}")

        code, _ = await self._run(f"docker pull {self.image}", timeout=600)

        cmd = (
            f"docker run -d --name {self.container_name} "
            f"--memory={self.memory_limit} "
            f"-v {self.workspace}:/workspace "
            f"--network host "
            f"{self.image} "
            f"sleep infinity"
        )
        code, output = await self._run(cmd)
        if code != 0:
            return False, f"Failed to start sandbox: {output}"

        self._running = True

        for setup_cmd in SETUP_COMMANDS:
            await self.execute(setup_cmd, timeout=300)

        return True, f"Sandbox started: {self.container_name} ({self.image})"

    async def stop(self) -> tuple[bool, str]:
        code, output = await self._run(f"docker stop {self.container_name} && docker rm {self.container_name}")
        self._running = False
        if code == 0:
            return True, "Sandbox stopped and removed."
        return False, output

    async def execute(self, command: str, timeout: int = 900, workdir: str = "/workspace") -> tuple[int, str]:
        if not self._running:
            return 1, "Sandbox not running. Use /sandbox start"
        escaped = command.replace("'", "'\\''")
        cmd = f"docker exec -w {workdir} {self.container_name} bash -c '{escaped}'"
        return await self._run(cmd, timeout=timeout)

    async def status(self) -> dict:
        if not self.is_docker_available:
            return {"running": False, "error": "Docker not available"}
        code, output = await self._run(f"docker inspect {self.container_name} 2>/dev/null")
        if code != 0:
            return {"running": False, "container": None}
        data = json.loads(output)[0]
        state = data.get("State", {})
        return {
            "running": state.get("Running", False),
            "container": self.container_name,
            "image": self.image,
            "memory": self.memory_limit,
            "workspace": self.workspace,
        }

    async def copy_to(self, local_path: str, container_path: str = "/workspace/") -> bool:
        code, _ = await self._run(f"docker cp {local_path} {self.container_name}:{container_path}")
        return code == 0

    async def copy_from(self, container_path: str, local_path: str) -> bool:
        code, _ = await self._run(f"docker cp {self.container_name}:{container_path} {local_path}")
        return code == 0

    @property
    def running(self) -> bool:
        return self._running
