"""JEV-style false-positive filter (second-opinion pass, fails open).

Mirrors Pentest-Swarm-AI `--jev`: an optional verification pass that
re-examines a candidate finding against evidence quality rules and
returns keep/discard + confidence. Off by default; fails open (on any
error the finding is KEPT so we never silently drop real vulns).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JevVerdict:
    keep: bool
    confidence: float  # 0.0 - 1.0
    reason: str
    adjusted_severity: str = ""


# Evidence signals that raise confidence the finding is REAL.
STRONG_EVIDENCE = [
    "request", "response", "status 200", "proof", "poc", "screenshot",
    "curl", "http/", "set-cookie", "token", "session", "database error",
    "stack trace", "query", "shell", "whoami", "uid=",
]

# Signals that suggest a scanner maybe / theoretical FP.
FP_SIGNALS = [
    "may be", "might be", "possibly", "theoretical", "could potentially",
    "unable to confirm", "no evidence", "not verified", "assumed",
]


class JevFilter:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def verify(self, title: str, detail: str = "", evidence: str = "",
               severity: str = "medium") -> JevVerdict:
        """Second-opinion pass. Fails open → keep on any error/uncertainty."""
        try:
            if not self.enabled:
                return JevVerdict(True, 0.5, "jev off — passthrough (fail open)")
            blob = f"{title}\n{detail}\n{evidence}".lower()
            if not blob.strip():
                return JevVerdict(True, 0.3, "empty finding — kept (fail open)")
            strong = sum(1 for s in STRONG_EVIDENCE if s in blob)
            fp = sum(1 for s in FP_SIGNALS if s in blob)
            has_poc = any(k in blob for k in ("poc", "proof", "curl", "screenshot", "whoami", "uid="))
            if has_poc and strong >= 2:
                return JevVerdict(True, 0.9, f"evidence-backed ({strong} signals)",
                                   adjusted_severity=severity)
            if fp >= 2 and strong == 0:
                return JevVerdict(False, 0.75,
                                   f"likely FP: {fp} hedge signals, no evidence")
            if strong >= 3:
                return JevVerdict(True, 0.8, f"strong evidence ({strong} signals)")
            # Uncertain → keep (fail open), downgrade confidence.
            adj = severity
            if strong == 0 and severity in ("critical", "high"):
                adj = "medium" if severity == "high" else "high"
                return JevVerdict(True, 0.4,
                                   "no concrete evidence — kept but downgraded (fail open)",
                                   adjusted_severity=adj)
            return JevVerdict(True, 0.55, "uncertain — kept (fail open)")
        except Exception:
            return JevVerdict(True, 0.3, "verifier error — kept (fail open)")
