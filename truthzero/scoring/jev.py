"""JEV false-positive filter (second-opinion pass, fails open).

Two layers, AND-gated on DROP:
1. builtin heuristic (local, free, offline) — always runs when enabled.
2. external TypeSafe Jev (opt-in, `TYPESAFE_API_KEY`) — consulted only for
   report-grade severities (>= `external_min_severity`, default high), so
   paid calls go to findings where an FP is expensive, not info noise.

A finding is DROPPED only if builtin AND external both say drop.
Conflict or abstain → keep + flag for human review. Off by default;
fails open everywhere (any error keeps the finding).
"""
from __future__ import annotations

from dataclasses import dataclass

_SEV_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0, "none": 0}


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
    def __init__(self, enabled: bool = False, backend: str = "auto",
                 external_min_severity: str = "high", _external=None):
        self.enabled = enabled
        self.backend = backend  # auto|builtin|external
        self.external_min_severity = external_min_severity
        self._external = _external  # injectable for tests

    def _external_backend(self):
        if self._external is not None:
            return self._external
        if self.backend == "builtin":
            return None
        try:
            from truthzero.scoring.jev_external import ExternalJevBackend
            be = ExternalJevBackend()
            return be if be.available() else None
        except Exception:
            return None

    def _consult_external(self, title: str, detail: str, evidence: str,
                          severity: str):
        """Returns ExternalVerdict, 'skipped', or None (abstain)."""
        if self.backend == "builtin":
            return "skipped"
        if _SEV_ORDER.get(severity.lower(), 0) < _SEV_ORDER.get(
                self.external_min_severity.lower(), 3):
            return "skipped"
        be = self._external_backend()
        if be is None:
            return "skipped"
        try:
            return be.verify(title, detail, evidence)
        except Exception:
            return None

    def verify(self, title: str, detail: str = "", evidence: str = "",
               severity: str = "medium") -> JevVerdict:
        """Second-opinion pass. Fails open → keep on any error/uncertainty."""
        try:
            if not self.enabled:
                return JevVerdict(True, 0.5, "jev off — passthrough (fail open)")
            builtin = self._builtin(title, detail, evidence, severity)
            if builtin.keep:
                return builtin
            # Builtin says DROP → AND-gate with external before discarding.
            ext = self._consult_external(title, detail, evidence, severity)
            if ext == "skipped":
                return JevVerdict(builtin.keep, builtin.confidence,
                                   builtin.reason + " [external skipped]",
                                   builtin.adjusted_severity)
            if ext is None:
                return JevVerdict(True, 0.45,
                                   f"{builtin.reason} — external abstained, kept for human review",
                                   severity)
            if ext.keep:
                return JevVerdict(True, 0.5,
                                   f"{builtin.reason} — external disagrees "
                                   f"(p={ext.probability:.2f}), kept for human review",
                                   severity)
            return JevVerdict(False, round(0.5 + ext.probability / 2, 2),
                               f"{builtin.reason} — external agrees "
                               f"(p={ext.probability:.2f})",
                               builtin.adjusted_severity)
        except Exception:
            return JevVerdict(True, 0.3, "verifier error — kept (fail open)")

    def _builtin(self, title: str, detail: str, evidence: str,
                 severity: str) -> JevVerdict:
        try:
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
