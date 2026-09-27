"""Self-correcting attacks — closed-loop replanning.

A failed step (401/403/415/429/5xx/timeout/empty) feeds back into a
mutation suggestion; the caller adjusts the request and retries.
Heals instead of dead-ending. Fails open (returns original on unknown).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class HealPlan:
    retry: bool
    mutated_headers: dict
    mutated_note: str
    backoff_s: float = 0.0


STATUS_RULES: list[tuple[str, str, dict, float]] = [
    # pattern, note, header mutation, backoff
    (r"401|unauthorized", "add/refresh auth: attach session cookie or JWT, retry once",
     {}, 0.0),
    (r"403|forbidden|waf|blocked", "try verb tamper (GET↔POST), case-flip path, or alternate encoding",
     {"X-HTTP-Method-Override": "GET"}, 1.0),
    (r"415|unsupported media|content-type", "switch Content-Type (json↔form↔xml) and retry",
     {"Content-Type": "application/json"}, 0.0),
    (r"429|rate.?limit|too many", "back off + jitter, shrink concurrency, retry once",
     {}, 5.0),
    (r"50[023]|bad gateway|timeout|timed out", "retry once with longer timeout; then mark flaky",
     {}, 3.0),
    (r"404|not found", "re-derive path from JS/crawl (no blind retry storm)",
     {}, 0.0),
]


def plan_heal(status_or_error: str | int) -> HealPlan:
    blob = str(status_or_error).lower()
    for pattern, note, headers, backoff in STATUS_RULES:
        if re.search(pattern, blob):
            return HealPlan(retry=True, mutated_headers=dict(headers),
                            mutated_note=note, backoff_s=backoff)
    return HealPlan(retry=False, mutated_headers={},
                    mutated_note="unknown failure — change approach, do not blind-retry")


def should_retry(status_or_error: str | int, attempt: int, max_attempts: int = 2) -> bool:
    if attempt >= max_attempts:
        return False
    return plan_heal(status_or_error).retry
