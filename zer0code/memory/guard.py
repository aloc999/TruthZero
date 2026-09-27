"""Memory-poisoning guard — MINJA/MemoryGraft-style defences (light).

The Hermes memory learns from sessions — including attacker-influenced
content (target responses, web pages). This guard screens lessons before
they are stored:
- drops prompt-injection directives (ignore previous instructions, etc.)
- drops system-prompt extraction echoes
- drops over-long / control-char-heavy blobs
- per-source quota so one session cannot flood memory

Fail open for the agent, fail closed for the store (suspicious = dropped).
"""
from __future__ import annotations

import re
from collections import defaultdict

INJECTION_RES = [
    re.compile(r"ignore (all )?previous instructions", re.I),
    re.compile(r"disregard (all )?(prior|previous|above)", re.I),
    re.compile(r"you are now (a|an) ", re.I),
    re.compile(r"system prompt\s*[:=]", re.I),
    re.compile(r"reveal (your|the) (system )?prompt", re.I),
    re.compile(r"jailbreak|DAN mode|developer mode", re.I),
    re.compile(r"exfiltrate|send .* to (attacker|evil|external)", re.I),
]

MAX_LESSON_LEN = 2000


class MemoryGuard:
    def __init__(self, per_source_quota: int = 50):
        self.per_source_quota = per_source_quota
        self._counts: dict[str, int] = defaultdict(int)

    def check(self, lesson: str, source: str = "session") -> tuple[bool, str]:
        """Returns (allowed, reason). Suspicious lessons are dropped."""
        if not lesson or not lesson.strip():
            return False, "empty lesson"
        if len(lesson) > MAX_LESSON_LEN:
            return False, f"lesson too long ({len(lesson)} > {MAX_LESSON_LEN})"
        ctrls = sum(1 for c in lesson if ord(c) < 32 and c not in "\n\t")
        if ctrls > 10:
            return False, "excess control characters"
        for rx in INJECTION_RES:
            if rx.search(lesson):
                return False, f"injection pattern blocked: {rx.pattern[:40]}"
        if self._counts[source] >= self.per_source_quota:
            return False, f"source quota exceeded ({source})"
        self._counts[source] += 1
        return True, "ok"

    def sanitize(self, lesson: str) -> str:
        """Best-effort clean for borderline input (strip controls, trim)."""
        clean = "".join(c for c in lesson if ord(c) >= 32 or c in "\n\t")
        return clean.strip()[:MAX_LESSON_LEN]
