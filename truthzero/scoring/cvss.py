"""CVSS v3.1 base-score calculator (FIRST spec).

Implements the official CVSS v3.1 equations so every TRUTHZERO finding
carries a vector + score + severity, like Pentest-Swarm-AI's stable
CVSS scoring. Fails open to 0.0/None on bad input.
"""
from __future__ import annotations

import math

# Metric weights per FIRST CVSS v3.1 specification.
AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
AC = {"L": 0.77, "H": 0.44}
PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}  # scope unchanged
PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}   # scope changed
UI = {"N": 0.85, "R": 0.62}
CIA = {"N": 0.0, "L": 0.22, "H": 0.56}

VALID = {
    "AV": set(AV), "AC": set(AC), "PR": set(PR_U),
    "UI": set(UI), "S": {"U", "C"},
    "C": set(CIA), "I": set(CIA), "A": set(CIA),
}


def _roundup(value: float) -> float:
    """CVSS Roundup: smallest number with 1 decimal >= value."""
    scaled = value * 100000
    if scaled % 10000 == 0:
        return scaled / 100000
    return (math.floor(scaled / 10000) + 1) / 10


def severity_from_score(score: float) -> str:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0.0:
        return "low"
    return "none"


def parse_vector(vector: str) -> dict[str, str]:
    metrics: dict[str, str] = {}
    v = vector.strip().upper()
    if v.startswith("CVSS:3.1/"):
        v = v[len("CVSS:3.1/"):]
    for part in v.split("/"):
        if ":" not in part:
            continue
        k, val = part.split(":", 1)
        metrics[k.strip()] = val.strip()
    return metrics


def cvss31_score(vector: str) -> tuple[float, str]:
    """Returns (base_score, severity). Fails open to (0.0, 'none')."""
    try:
        m = parse_vector(vector)
        for k, allowed in VALID.items():
            if m.get(k) not in allowed:
                return 0.0, "none"
        scope_changed = m["S"] == "C"
        iss = 1 - (1 - CIA[m["C"]]) * (1 - CIA[m["I"]]) * (1 - CIA[m["A"]])
        if scope_changed:
            impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)
            impact = max(impact, 0.0)
        else:
            impact = 6.42 * iss
        pr = PR_C[m["PR"]] if scope_changed else PR_U[m["PR"]]
        exploit = 8.22 * AV[m["AV"]] * AC[m["AC"]] * pr * UI[m["UI"]]
        if impact <= 0:
            return 0.0, "none"
        if scope_changed:
            base = _roundup(min(1.08 * (impact + exploit), 10.0))
        else:
            base = _roundup(min(impact + exploit, 10.0))
        return round(base, 1), severity_from_score(base)
    except Exception:
        return 0.0, "none"


# Sensible default vectors per vuln class (so agents can score without a full vector).
DEFAULT_VECTORS: dict[str, str] = {
    "rce": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    "sqli": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H",
    "ssrf": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:L/A:N",
    "idor": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:L/A:N",
    "bola": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
    "xss": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
    "ssti": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H",
    "auth_bypass": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
    "jwt_forgery": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L",
    "mass_assignment": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:H/A:N",
    "takeover": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:N",
    "info_disclosure": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
}


def score_class(vuln_class: str, vector: str = "") -> tuple[float, str, str]:
    """Score by class with optional vector override. Returns (score, severity, vector)."""
    v = vector or DEFAULT_VECTORS.get(vuln_class.lower(), "")
    if not v:
        return 0.0, "none", ""
    score, sev = cvss31_score(v)
    return score, sev, v
