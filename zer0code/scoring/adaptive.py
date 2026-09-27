"""Adaptive attack-path scoring — graded pheromone.

The swarm generates candidate attack strategies, scores them against
live blackboard state, pursues the best first, and reinforces what works.
Mirrors Pentest-Swarm-AI `--jev-adaptive`. Fails open (falls back to
static priority order).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from zer0code.swarm.blackboard import Blackboard
from zer0code.scoring.cvss import score_class


@dataclass
class AttackPath:
    name: str
    vuln_class: str
    description: str
    needs_types: list[str] = field(default_factory=list)  # blackboard ftypes that enable it
    base_priority: float = 0.5
    score: float = 0.0
    cvss: float = 0.0
    severity: str = ""

    def compute(self, board: Blackboard) -> float:
        try:
            hot_types = {f.ftype for f in board.hot()}
            coverage = (len(set(self.needs_types) & hot_types) / len(self.needs_types)
                        if self.needs_types else 0.5)
            cvss_score, sev, _ = score_class(self.vuln_class)
            self.cvss, self.severity = cvss_score, sev
            # live-state score: base + coverage boost + cvss weight
            self.score = round(
                0.3 * self.base_priority + 0.4 * coverage + 0.3 * (cvss_score / 10.0), 3
            )
            return self.score
        except Exception:
            self.score = self.base_priority
            return self.score


DEFAULT_PATHS: list[AttackPath] = [
    AttackPath("bola-idor-chain", "bola", "Cross-user object access via mined refs",
               ["OBJECT_REF", "ENDPOINT"], 0.9),
    AttackPath("jwt-forgery", "jwt_forgery", "JWT alg confusion / none / weak secret",
               ["ENDPOINT", "TECH"], 0.8),
    AttackPath("mass-assignment", "mass_assignment", "Extra-field role escalation",
               ["ENDPOINT"], 0.7),
    AttackPath("ssrf-to-metadata", "ssrf", "SSRF → cloud metadata / internal",
               ["ENDPOINT", "TECH"], 0.85),
    AttackPath("sqli-chain", "sqli", "Injection in mined params", ["ENDPOINT", "OBJECT_REF"], 0.85),
    AttackPath("xss-chain", "xss", "Reflected/stored XSS via params", ["ENDPOINT"], 0.6),
    AttackPath("ssti-chain", "ssti", "Template injection in error/preview paths",
               ["ENDPOINT", "TECH"], 0.75),
    AttackPath("auth-bypass", "auth_bypass", "Force-browse / verb tamper / session",
               ["ENDPOINT"], 0.7),
    AttackPath("subdomain-takeover", "takeover", "Dangling DNS → claim",
               ["TAKEOVER_CANDIDATE", "SUBDOMAIN"], 0.65),
]


class AdaptiveScorer:
    """Ranks attack paths against live board; reinforces winners."""

    def __init__(self, paths: list[AttackPath] | None = None):
        self.paths = [AttackPath(p.name, p.vuln_class, p.description,
                                 list(p.needs_types), p.base_priority)
                      for p in (paths or DEFAULT_PATHS)]
        self._wins: dict[str, int] = {}

    def rank(self, board: Blackboard) -> list[AttackPath]:
        try:
            for p in self.paths:
                p.compute(board)
                p.score = round(p.score + 0.05 * self._wins.get(p.name, 0), 3)
            return sorted(self.paths, key=lambda p: p.score, reverse=True)
        except Exception:
            return sorted(self.paths, key=lambda p: p.base_priority, reverse=True)

    def reinforce(self, path_name: str) -> None:
        self._wins[path_name] = self._wins.get(path_name, 0) + 1

    def top(self, board: Blackboard, n: int = 3) -> list[AttackPath]:
        return self.rank(board)[:n]
