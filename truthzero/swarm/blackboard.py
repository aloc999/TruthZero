"""Stigmergic blackboard with pheromone decay.

Each finding has a pheromone weight that spikes to 1.0 on write and
decays exponentially. Different finding types decay at different rates
(config-driven half-lives). Agents fire when weight > their threshold.

Ports the Pentest-Swarm-AI pheromone-lifecycle concept to Python:
- PORT_OPEN stays hot for hours; SESSION for minutes.
- Above 0.5 the exploit agent fires, above 0.2 the classifier fires,
  below 0.2 the finding goes stale.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# Half-life in seconds per finding type (config-driven, mirrors Pentest-Swarm-AI).
FINDING_HALF_LIVES: dict[str, float] = {
    "PORT_OPEN": 4 * 3600.0,
    "SERVICE": 4 * 3600.0,
    "SUBDOMAIN": 6 * 3600.0,
    "ENDPOINT": 6 * 3600.0,
    "TECH": 6 * 3600.0,
    "VULN": 2 * 3600.0,
    "VULN_CONFIRMED": 8 * 3600.0,
    "CREDS": 8 * 3600.0,
    "SESSION": 15 * 60.0,
    "OBJECT_REF": 2 * 3600.0,   # mined ids/UUIDs/emails for BOLA probing
    "SECRET": 4 * 3600.0,
    "TAKEOVER_CANDIDATE": 3 * 3600.0,
    "NOTE": 1 * 3600.0,
}

DEFAULT_HALF_LIFE = 2 * 3600.0

# Thresholds (mirror Pentest-Swarm-AI diagram)
EXPLOIT_THRESHOLD = 0.5
CLASSIFY_THRESHOLD = 0.2


@dataclass
class Finding:
    finding_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    ftype: str = "NOTE"
    title: str = ""
    detail: str = ""
    severity: str = "info"  # critical|high|medium|low|info
    target: str = ""
    evidence: str = ""
    agent: str = ""
    created_at: float = field(default_factory=time.time)
    weight: float = 1.0  # pheromone, spikes to 1.0 on write

    def decayed_weight(self, now: float | None = None) -> float:
        now = now if now is not None else time.time()
        half_life = FINDING_HALF_LIVES.get(self.ftype, DEFAULT_HALF_LIFE)
        age = max(0.0, now - self.created_at)
        return self.weight * (0.5 ** (age / half_life))

    def reinforce(self, amount: float = 0.3) -> None:
        """Successful follow-up reinforces the pheromone (graded pheromone)."""
        self.weight = min(1.0, self.weight + amount)
        self.created_at = time.time()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["current_weight"] = round(self.decayed_weight(), 3)
        return d


class Blackboard:
    """Shared stigmergic board. Thread-safe enough for asyncio (single loop)."""

    def __init__(self, persist_path: str | None = None):
        self._findings: dict[str, Finding] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self.load()

    # -- writes ---------------------------------------------------------
    def write(self, finding: Finding) -> str:
        self._findings[finding.finding_id] = finding
        self._autosave()
        return finding.finding_id

    def add(self, ftype: str, title: str, detail: str = "", **kwargs) -> str:
        f = Finding(ftype=ftype.upper(), title=title, detail=detail, **kwargs)
        return self.write(f)

    def reinforce(self, finding_id: str, amount: float = 0.3) -> bool:
        f = self._findings.get(finding_id)
        if not f:
            return False
        f.reinforce(amount)
        self._autosave()
        return True

    def remove(self, finding_id: str) -> bool:
        """Delete a finding (e.g. JEV-agreed false positive)."""
        if finding_id in self._findings:
            del self._findings[finding_id]
            self._autosave()
            return True
        return False

    # -- reads ----------------------------------------------------------
    def hot(self, threshold: float = CLASSIFY_THRESHOLD,
            ftypes: list[str] | None = None) -> list[Finding]:
        now = time.time()
        out = []
        for f in self._findings.values():
            if ftypes and f.ftype not in ftypes:
                continue
            if f.decayed_weight(now) >= threshold:
                out.append(f)
        out.sort(key=lambda f: f.decayed_weight(now), reverse=True)
        return out

    def exploit_candidates(self) -> list[Finding]:
        return self.hot(EXPLOIT_THRESHOLD)

    def classify_candidates(self) -> list[Finding]:
        return self.hot(CLASSIFY_THRESHOLD)

    def all(self) -> list[Finding]:
        return list(self._findings.values())

    def get(self, finding_id: str) -> Optional[Finding]:
        return self._findings.get(finding_id)

    def prune_stale(self, threshold: float = 0.05) -> int:
        now = time.time()
        stale = [fid for fid, f in self._findings.items()
                 if f.decayed_weight(now) < threshold]
        for fid in stale:
            del self._findings[fid]
        if stale:
            self._autosave()
        return len(stale)

    # -- stats ----------------------------------------------------------
    def summary(self) -> dict:
        now = time.time()
        by_type: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        for f in self._findings.values():
            by_type[f.ftype] = by_type.get(f.ftype, 0) + 1
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
        hot = sum(1 for f in self._findings.values()
                  if f.decayed_weight(now) >= CLASSIFY_THRESHOLD)
        return {
            "total": len(self._findings),
            "hot": hot,
            "by_type": by_type,
            "by_severity": by_sev,
        }

    def prompt_context(self, max_findings: int = 20) -> str:
        """Compact blackboard snapshot injected into agent system prompts."""
        hot = self.hot()[:max_findings]
        if not hot:
            return "BLACKBOARD: empty — no findings yet."
        lines = [f"BLACKBOARD ({len(self._findings)} findings, {len(hot)} hot):"]
        for f in hot:
            lines.append(
                f"  [{f.ftype} w={f.decayed_weight():.2f} {f.severity}] "
                f"{f.title} (target={f.target or '-'}, id={f.finding_id})"
            )
        return "\n".join(lines)

    # -- persistence ----------------------------------------------------
    def save(self, path: str | None = None) -> None:
        p = Path(path) if path else self._persist_path
        if not p:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(f) for f in self._findings.values()]
        p.write_text(json.dumps(data, indent=2))

    def load(self, path: str | None = None) -> int:
        p = Path(path) if path else self._persist_path
        if not p or not p.exists():
            return 0
        try:
            data = json.loads(p.read_text())
        except Exception:
            return 0
        count = 0
        for item in data:
            try:
                item.pop("current_weight", None)
                self._findings[item.get("finding_id", str(uuid.uuid4())[:8])] = Finding(**item)
                count += 1
            except Exception:
                continue
        return count

    def _autosave(self) -> None:
        if self._persist_path:
            try:
                self.save()
            except Exception:
                pass
