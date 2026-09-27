import asyncio
import os
import shutil
import sys
from pathlib import Path


class Doctor:
    def __init__(self):
        self.checks = []

    async def run_all(self) -> list[dict]:
        self.checks = []
        self._check_python()
        self._check_api_keys()
        self._check_config()
        self._check_memory_db()
        self._check_tools()
        self._check_disk()
        self._check_git()
        self._check_network()
        return self.checks

    def _pass(self, name: str, detail: str = ""):
        self.checks.append({"name": name, "status": "pass", "detail": detail})

    def _warn(self, name: str, detail: str):
        self.checks.append({"name": name, "status": "warn", "detail": detail})

    def _fail(self, name: str, detail: str):
        self.checks.append({"name": name, "status": "fail", "detail": detail})

    def _check_python(self):
        v = sys.version_info
        if v.major == 3 and v.minor >= 10:
            self._pass("Python version", f"{v.major}.{v.minor}.{v.micro}")
        else:
            self._fail("Python version", f"{v.major}.{v.minor} — need 3.10+")

    def _check_api_keys(self):
        keys = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
            "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY"),
            "ZHIPU_API_KEY": os.environ.get("ZHIPU_API_KEY", os.environ.get("ZHIPUAI_API_KEY")),
            "TYPESAFE_API_KEY": os.environ.get("TYPESAFE_API_KEY"),
        }
        found = [k for k, v in keys.items() if v]
        if found:
            self._pass("API keys", f"Found: {', '.join(found)}")
        else:
            self._warn("API keys", "No API keys set. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY")
        if os.environ.get("TYPESAFE_API_KEY"):
            self._pass("Jev", "external TypeSafe backend ready (opt-in second layer)")
        else:
            self._pass("Jev", "builtin heuristic only (set TYPESAFE_API_KEY for external second opinion)")

    def _check_config(self):
        config_path = Path.home() / ".truthzero" / "config.json"
        if config_path.exists():
            try:
                import json
                data = json.loads(config_path.read_text())
                from truthzero.validation import ConfigValidator
                errors = ConfigValidator.validate(data)
                if errors:
                    self._warn("Config", f"{len(errors)} validation issue(s): {errors[0]}")
                else:
                    self._pass("Config", str(config_path))
            except Exception as e:
                self._fail("Config", f"Parse error: {e}")
        else:
            self._warn("Config", "No config file — will use defaults")

    def _check_memory_db(self):
        db_path = Path.home() / ".truthzero" / "memory.db"
        if db_path.exists():
            size = db_path.stat().st_size
            self._pass("Memory DB", f"{size / 1024:.1f} KB")
        else:
            self._pass("Memory DB", "Will be created on first run")

    def _check_tools(self):
        tools = {
            "git": "Version control",
            "nmap": "Port scanning",
            "ffuf": "Directory fuzzing",
            "nuclei": "Vulnerability scanning",
            "subfinder": "Subdomain enumeration",
            "hashcat": "Hash cracking",
            "john": "Hash cracking",
            "gh": "GitHub CLI",
            "curl": "HTTP requests",
            "dig": "DNS lookup",
            "whois": "WHOIS lookup",
        }
        found = []
        missing = []
        for tool, desc in tools.items():
            if shutil.which(tool):
                found.append(tool)
            else:
                missing.append(tool)

        if found:
            self._pass("External tools", f"{len(found)} found: {', '.join(found)}")
        if missing:
            self._warn("Missing tools", f"{', '.join(missing)} — some features limited")

    def _check_disk(self):
        try:
            home = Path.home()
            st = os.statvfs(str(home))
            free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
            if free_gb < 1:
                self._warn("Disk space", f"{free_gb:.1f} GB free — low")
            else:
                self._pass("Disk space", f"{free_gb:.1f} GB free")
        except Exception:
            self._pass("Disk space", "Check skipped")

    def _check_git(self):
        if shutil.which("git"):
            self._pass("Git", shutil.which("git"))
        else:
            self._fail("Git", "Not installed — git tools won't work")

    def _check_network(self):
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            self._pass("Network", "Connected")
        except Exception:
            self._warn("Network", "No internet — only Ollama (local) will work")

    @property
    def has_failures(self) -> bool:
        return any(c["status"] == "fail" for c in self.checks)

    @property
    def summary(self) -> str:
        passes = sum(1 for c in self.checks if c["status"] == "pass")
        warns = sum(1 for c in self.checks if c["status"] == "warn")
        fails = sum(1 for c in self.checks if c["status"] == "fail")
        return f"{passes} passed, {warns} warnings, {fails} failures"
