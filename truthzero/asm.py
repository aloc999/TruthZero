"""ASM snapshot diffing + CI quality gate.

- ASMSnapshot: capture subdomains/hosts/endpoints/ports, save JSON, diff
  vs previous (added/removed). New assets go hot on the blackboard.
- CIGate: evaluate SARIF or finding dicts against fail_on severities;
  returns exit code (0 pass, 2 gate failed) for CI pipelines.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ASMSnapshot:
    target: str = ""
    created_at: float = 0.0
    subdomains: list[str] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)
    endpoints: list[str] = field(default_factory=list)
    ports: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def save(self, path: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=2))
        return str(p)

    @classmethod
    def load(cls, path: str) -> "ASMSnapshot":
        data = json.loads(Path(path).read_text())
        return cls(**{k: data.get(k, v) for k, v in
                      [("target", ""), ("created_at", 0.0), ("subdomains", []),
                       ("hosts", []), ("endpoints", []), ("ports", [])]})

    def diff(self, previous: "ASMSnapshot") -> dict:
        out = {}
        for key in ("subdomains", "hosts", "endpoints", "ports"):
            old, new = set(getattr(previous, key)), set(getattr(self, key))
            out[key] = {"added": sorted(new - old), "removed": sorted(old - new),
                        "count": len(new)}
        out["target"] = self.target
        return out

    def format_diff(self, d: dict) -> str:
        lines = [f"ASM delta for {d.get('target', '')}:"]
        for key in ("subdomains", "hosts", "endpoints", "ports"):
            added, removed = d[key]["added"], d[key]["removed"]
            lines.append(f"  {key}: {d[key]['count']} total "
                         f"(+{len(added)} new, -{len(removed)} gone)")
            for a in added[:10]:
                lines.append(f"    + {a}")
            for r in removed[:10]:
                lines.append(f"    - {r}")
        return "\n".join(lines)


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "none": 0}


class CIGate:
    """Fail CI when findings meet/exceed fail_on severities. Exit 2 = gate failed."""

    def __init__(self, fail_on: tuple[str, ...] = ("high", "critical")):
        self.fail_on = tuple(fail_on)

    def threshold_level(self) -> int:
        return min(SEVERITY_ORDER.get(s, 3) for s in self.fail_on)

    def evaluate(self, findings: list[dict]) -> dict:
        level = self.threshold_level()
        blocking = [f for f in findings
                    if SEVERITY_ORDER.get(str(f.get("severity", "info")).lower(), 0) >= level]
        passed = not blocking
        return {
            "passed": passed,
            "exit_code": 0 if passed else 2,
            "fail_on": list(self.fail_on),
            "blocking": len(blocking),
            "total": len(findings),
            "top": [f.get("title", "")[:120] for f in blocking[:10]],
        }

    def evaluate_sarif(self, sarif: dict) -> dict:
        results = (sarif.get("runs", [{}])[0].get("results", [])
                   if sarif.get("runs") else [])
        sev_of = {"error": "high", "warning": "medium", "note": "low"}
        findings = [{"severity": sev_of.get(r.get("level", "warning"), "medium"),
                     "title": (r.get("message", {}) or {}).get("text", "")[:120]}
                    for r in results]
        return self.evaluate(findings)
