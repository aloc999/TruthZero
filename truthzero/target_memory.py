import json
import os
import time
from pathlib import Path
from typing import Optional


TARGET_DIR = Path.home() / ".truthzero" / "targets"


class TargetMemory:
    def __init__(self, target: str):
        self.target = target
        self._data = {
            "target": target,
            "first_seen": time.time(),
            "last_updated": time.time(),
            "subdomains": [],
            "endpoints": [],
            "technologies": [],
            "ports": [],
            "vulnerabilities": [],
            "waf_bypasses": [],
            "sensitive_params": [],
            "auth_endpoints": [],
            "api_endpoints": [],
            "notes": [],
            "headers": {},
        }
        self._load()

    def _filepath(self) -> Path:
        safe_name = self.target.replace("://", "_").replace("/", "_").replace(".", "_").replace(":", "_")
        TARGET_DIR.mkdir(parents=True, exist_ok=True)
        return TARGET_DIR / f"{safe_name}.json"

    def _load(self):
        fp = self._filepath()
        if fp.exists():
            try:
                self._data = json.loads(fp.read_text())
            except Exception:
                pass

    def save(self):
        self._data["last_updated"] = time.time()
        self._filepath().write_text(json.dumps(self._data, indent=2))

    def add_subdomain(self, subdomain: str):
        if subdomain not in self._data["subdomains"]:
            self._data["subdomains"].append(subdomain)
            self.save()

    def add_endpoint(self, endpoint: str, method: str = "GET", status: int = 0):
        entry = {"path": endpoint, "method": method, "status": status}
        if entry not in self._data["endpoints"]:
            self._data["endpoints"].append(entry)
            self.save()

    def add_technology(self, tech: str):
        if tech not in self._data["technologies"]:
            self._data["technologies"].append(tech)
            self.save()

    def add_port(self, port: int, service: str = ""):
        entry = {"port": port, "service": service}
        if entry not in self._data["ports"]:
            self._data["ports"].append(entry)
            self.save()

    def add_vulnerability(self, vuln: dict):
        self._data["vulnerabilities"].append({**vuln, "found_at": time.time()})
        self.save()

    def add_waf_bypass(self, bypass: str):
        if bypass not in self._data["waf_bypasses"]:
            self._data["waf_bypasses"].append(bypass)
            self.save()

    def add_sensitive_param(self, param: str, location: str = ""):
        entry = {"param": param, "location": location}
        if entry not in self._data["sensitive_params"]:
            self._data["sensitive_params"].append(entry)
            self.save()

    def add_note(self, note: str):
        self._data["notes"].append({"text": note, "time": time.time()})
        self.save()

    def get_context_prompt(self) -> str:
        parts = [f"TARGET INTELLIGENCE for {self.target}:"]
        if self._data["subdomains"]:
            parts.append(f"  Subdomains ({len(self._data['subdomains'])}): {', '.join(self._data['subdomains'][:20])}")
        if self._data["technologies"]:
            parts.append(f"  Tech stack: {', '.join(self._data['technologies'])}")
        if self._data["ports"]:
            ports_str = ", ".join(f"{p['port']}/{p['service']}" for p in self._data["ports"][:20])
            parts.append(f"  Open ports: {ports_str}")
        if self._data["endpoints"]:
            parts.append(f"  Known endpoints: {len(self._data['endpoints'])}")
        if self._data["vulnerabilities"]:
            parts.append(f"  Known vulns: {len(self._data['vulnerabilities'])}")
            for v in self._data["vulnerabilities"][:5]:
                parts.append(f"    - {v.get('title', v.get('type', 'unknown'))}")
        if self._data["waf_bypasses"]:
            parts.append(f"  WAF bypasses: {', '.join(self._data['waf_bypasses'][:5])}")
        if self._data["sensitive_params"]:
            params = [p["param"] for p in self._data["sensitive_params"][:10]]
            parts.append(f"  Sensitive params: {', '.join(params)}")
        return "\n".join(parts)

    @property
    def summary(self) -> dict:
        return {
            "target": self.target,
            "subdomains": len(self._data["subdomains"]),
            "endpoints": len(self._data["endpoints"]),
            "technologies": self._data["technologies"],
            "ports": len(self._data["ports"]),
            "vulnerabilities": len(self._data["vulnerabilities"]),
            "notes": len(self._data["notes"]),
        }

    @staticmethod
    def list_targets() -> list[str]:
        if not TARGET_DIR.exists():
            return []
        targets = []
        for f in TARGET_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                targets.append(data.get("target", f.stem))
            except Exception:
                targets.append(f.stem)
        return targets
