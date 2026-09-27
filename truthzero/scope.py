import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScopeConfig:
    in_scope: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    wildcard_domains: list[str] = field(default_factory=list)
    ip_ranges: list[str] = field(default_factory=list)
    notes: str = ""


class ScopeManager:
    def __init__(self):
        self._config = ScopeConfig()
        self._enabled = False

    def load_from_file(self, path: str = "scope.json") -> bool:
        filepath = Path(path)
        if not filepath.exists():
            return False
        try:
            data = json.loads(filepath.read_text())
            self._config = ScopeConfig(
                in_scope=data.get("in_scope", []),
                out_of_scope=data.get("out_of_scope", []),
                wildcard_domains=data.get("wildcard_domains", []),
                ip_ranges=data.get("ip_ranges", []),
                notes=data.get("notes", ""),
            )
            self._enabled = True
            return True
        except Exception:
            return False

    def save_to_file(self, path: str = "scope.json"):
        data = {
            "in_scope": self._config.in_scope,
            "out_of_scope": self._config.out_of_scope,
            "wildcard_domains": self._config.wildcard_domains,
            "ip_ranges": self._config.ip_ranges,
            "notes": self._config.notes,
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def add_in_scope(self, target: str):
        if target not in self._config.in_scope:
            self._config.in_scope.append(target)
        self._enabled = True

    def add_out_of_scope(self, target: str):
        if target not in self._config.out_of_scope:
            self._config.out_of_scope.append(target)

    def add_wildcard(self, domain: str):
        if not domain.startswith("*."):
            domain = f"*.{domain}"
        if domain not in self._config.wildcard_domains:
            self._config.wildcard_domains.append(domain)
        self._enabled = True

    def is_in_scope(self, target: str) -> bool:
        if not self._enabled:
            return True
        target_lower = target.lower().strip()
        for pattern in self._config.out_of_scope:
            if fnmatch.fnmatch(target_lower, pattern.lower()):
                return False
            if pattern.lower() in target_lower:
                return False
        for pattern in self._config.in_scope:
            if fnmatch.fnmatch(target_lower, pattern.lower()):
                return True
            if pattern.lower() in target_lower:
                return True
        for pattern in self._config.wildcard_domains:
            domain = pattern.replace("*.", "")
            if target_lower.endswith(domain.lower()):
                return True
        if not self._config.in_scope and not self._config.wildcard_domains:
            return True
        return False

    def check_url(self, url: str) -> bool:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = parsed.hostname or ""
            return self.is_in_scope(host)
        except Exception:
            return self.is_in_scope(url)

    def check_command(self, command: str) -> tuple[bool, str]:
        if not self._enabled:
            return True, ""
        ip_pattern = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
        domain_pattern = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b')
        targets = set()
        for match in ip_pattern.finditer(command):
            targets.add(match.group())
        for match in domain_pattern.finditer(command):
            t = match.group()
            if not t.endswith(('.py', '.js', '.txt', '.json', '.md', '.sh', '.yml', '.yaml', '.toml', '.cfg', '.conf', '.log', '.csv', '.xml', '.html')):
                targets.add(t)
        for target in targets:
            if not self.is_in_scope(target):
                return False, f"Target '{target}' is OUT OF SCOPE"
        return True, ""

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def summary(self) -> dict:
        return {
            "enabled": self._enabled,
            "in_scope": self._config.in_scope,
            "out_of_scope": self._config.out_of_scope,
            "wildcards": self._config.wildcard_domains,
            "notes": self._config.notes,
        }

    def format_display(self) -> str:
        lines = []
        if not self._enabled:
            return "  Scope: not configured (/scope add <target>)"
        lines.append(f"  In scope ({len(self._config.in_scope)}):")
        for t in self._config.in_scope:
            lines.append(f"    {t}")
        for t in self._config.wildcard_domains:
            lines.append(f"    {t}")
        if self._config.out_of_scope:
            lines.append(f"  Out of scope ({len(self._config.out_of_scope)}):")
            for t in self._config.out_of_scope:
                lines.append(f"    {t}")
        if self._config.notes:
            lines.append(f"  Notes: {self._config.notes}")
        return "\n".join(lines)
