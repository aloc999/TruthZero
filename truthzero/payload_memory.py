import json
import time
from pathlib import Path

PAYLOAD_DIR = Path.home() / ".truthzero" / "payloads"


class PayloadMemory:
    def __init__(self, target: str = ""):
        self.target = target
        self._data = {"target": target, "entries": {}}
        if target:
            self._load()

    def _filepath(self) -> Path:
        safe = self.target.replace("://", "_").replace("/", "_").replace(".", "_").replace(":", "_")
        PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
        return PAYLOAD_DIR / f"{safe}_payloads.json"

    def _load(self):
        fp = self._filepath()
        if fp.exists():
            try:
                self._data = json.loads(fp.read_text())
            except Exception:
                pass

    def save(self):
        if self.target:
            self._filepath().write_text(json.dumps(self._data, indent=2))

    def _key(self, parameter: str, vuln_type: str) -> str:
        return f"{parameter}:{vuln_type}"

    def record_attempt(self, parameter: str, vuln_type: str, payload: str, success: bool, status_code: int = 0):
        key = self._key(parameter, vuln_type)
        if key not in self._data["entries"]:
            self._data["entries"][key] = {"succeeded": [], "failed": [], "attempts": 0}
        entry = self._data["entries"][key]
        entry["attempts"] += 1
        record = {"payload": payload[:200], "status": status_code, "time": time.time()}
        if success:
            if payload not in [r["payload"] for r in entry["succeeded"]]:
                entry["succeeded"].append(record)
        else:
            if payload not in [r["payload"] for r in entry["failed"]]:
                entry["failed"].append(record)
        self.save()

    def should_skip(self, parameter: str, vuln_type: str, payload: str) -> bool:
        key = self._key(parameter, vuln_type)
        entry = self._data["entries"].get(key, {})
        failed = entry.get("failed", [])
        return payload[:200] in [r["payload"] for r in failed]

    def get_working_payloads(self, parameter: str, vuln_type: str) -> list[str]:
        key = self._key(parameter, vuln_type)
        entry = self._data["entries"].get(key, {})
        return [r["payload"] for r in entry.get("succeeded", [])]

    def get_failed_payloads(self, parameter: str, vuln_type: str) -> list[str]:
        key = self._key(parameter, vuln_type)
        entry = self._data["entries"].get(key, {})
        return [r["payload"] for r in entry.get("failed", [])]

    def filter_payloads(self, parameter: str, vuln_type: str, payloads: list[str]) -> list[str]:
        return [p for p in payloads if not self.should_skip(parameter, vuln_type, p)]

    def get_stats(self) -> dict:
        total_attempts = sum(e.get("attempts", 0) for e in self._data["entries"].values())
        total_success = sum(len(e.get("succeeded", [])) for e in self._data["entries"].values())
        total_failed = sum(len(e.get("failed", [])) for e in self._data["entries"].values())
        return {
            "target": self.target,
            "parameters_tested": len(self._data["entries"]),
            "total_attempts": total_attempts,
            "successful": total_success,
            "failed": total_failed,
            "skip_rate": f"{(total_failed / max(total_attempts, 1)) * 100:.0f}%",
        }

    def get_context_prompt(self) -> str:
        if not self._data["entries"]:
            return ""
        parts = [f"PAYLOAD MEMORY for {self.target}:"]
        for key, entry in list(self._data["entries"].items())[:10]:
            succeeded = len(entry.get("succeeded", []))
            failed = len(entry.get("failed", []))
            parts.append(f"  {key}: {succeeded} working, {failed} failed, {entry.get('attempts', 0)} total")
            for s in entry.get("succeeded", [])[:3]:
                parts.append(f"    ✓ {s['payload'][:80]}")
        return "\n".join(parts)
