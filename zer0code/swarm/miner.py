"""Response miner — turn every response into blackboard findings.

Runtime reaction to discoveries: mine URLs, params, object refs, emails,
secrets, and API paths from ANY text (HTTP responses, JS, crawl output).
One leaked id becomes cross-endpoint BOLA probes nobody scripted.
"""
from __future__ import annotations

import re

URL_RE = re.compile(r'https?://[^\s"\'<>\\]+')
PATH_RE = re.compile(r'(?:"|\s)(/[a-zA-Z0-9_\-./]{2,120}?)(?:"|\s|,)')
PARAM_RE = re.compile(r'[?&]([a-zA-Z_][\w\-]{0,40})=')
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+')
SECRET_RE = re.compile(
    r'(?i)(api[_-]?key|secret|token|passwd|password|aws_|sk-|ghp_|xoxb-|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
    r'\s*[:=]\s*["\']?([\w\-./+]{8,120})')
UUID_RE = re.compile(
    r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.I)
NUMID_RE = re.compile(r'(?:"|\b)(id|user_id|account_id|order_id|invoice_id|patient_id)"?\s*[:=]\s*"?(\d{1,12})', re.I)


def mine(text: str, source: str = "", target: str = "") -> list[dict]:
    """Extract structured leads. Returns finding-dicts (no board write here)."""
    if not text:
        return []
    blob = text[:50000]
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(ftype: str, title: str, severity: str = "info"):
        key = (ftype, title)
        if key not in seen:
            seen.add(key)
            out.append({"ftype": ftype, "title": title[:200], "severity": severity,
                        "target": target, "detail": f"mined from {source or 'response'}"})

    for m in URL_RE.finditer(blob):
        add("ENDPOINT", m.group(0)[:200])
        if len(seen) > 40:
            break
    for m in PATH_RE.finditer(blob):
        p = m.group(1)
        if "." in p.split("/")[-1] and not p.endswith((".js", ".json", ".api", "/")):
            continue
        if len(p) > 6:
            add("ENDPOINT", p)
    params = sorted(set(PARAM_RE.findall(blob)))
    for p in params[:20]:
        add("OBJECT_REF", f"param: {p}")
    for m in EMAIL_RE.finditer(blob):
        add("OBJECT_REF", f"email: {m.group(0)[:80]}")
    for m in UUID_RE.finditer(blob):
        add("OBJECT_REF", f"uuid: {m.group(0)}")
    for m in NUMID_RE.finditer(blob):
        add("OBJECT_REF", f"{m.group(1)}={m.group(2)}")
    for m in SECRET_RE.finditer(blob):
        add("SECRET", f"{m.group(1)} in {source or 'response'}", "high")
    return out[:60]
