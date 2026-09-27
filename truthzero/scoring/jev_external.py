"""External Jev backend — TypeSafe System One judgment API (opt-in).

Real Jev (https://api.typesafe.ai, POST /v1/systemone) answers typed
claim-vs-evidence questions with calibrated probabilities. Used ONLY as
an opt-in second layer for report-grade findings:

- Needs TYPESAFE_API_KEY (never send client target data without consent —
  responses may contain PII/creds; check your engagement rules first).
- Thresholds per ecosystem convention: >= 0.60 keep, <= 0.40 drop,
  in-between = abstain (caller fails open).
- ANY transport/schema surprise → return None (abstain), caller falls
  back to the builtin heuristic. External never hard-drops alone;
  JevFilter AND-gates it with builtin.

Schema below follows TypeSafe's documented System One surface
(state + model + typed questions → answers + usage). Parsing is
defensive: unknown shapes abstain instead of guessing.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"

KEEP_AT = 0.60
DROP_AT = 0.40


@dataclass
class ExternalVerdict:
    keep: bool
    probability: float
    raw: dict


def api_key_from_env() -> str:
    return os.environ.get("TYPESAFE_API_KEY", "")


def base_url_from_env() -> str:
    return os.environ.get("TYPESAFE_BASE_URL", DEFAULT_BASE_URL)


class ExternalJevBackend:
    def __init__(self, api_key: str = "", base_url: str = "",
                 model: str = DEFAULT_MODEL, timeout: float = 20.0):
        self.api_key = api_key or api_key_from_env()
        self.base_url = (base_url or base_url_from_env()).rstrip("/")
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout

    def available(self) -> bool:
        return bool(self.api_key)

    def _question_payload(self, title: str, detail: str, evidence: str) -> dict:
        state = (f"Vulnerability finding under review.\n"
                 f"Claim: {title}\n"
                 f"Detail: {detail[:2000]}\n"
                 f"Evidence: {evidence[:4000]}")
        return {
            "model": self.model,
            "state": state,
            "questions": [{
                "id": "supported",
                "question": ("Is the vulnerability claim directly supported "
                             "by the quoted evidence?"),
                "type": "noul",
            }],
        }

    @staticmethod
    def _extract_probability(data: dict) -> float | None:
        """Pull a 0..1 support probability from known answer shapes."""
        try:
            answers = data.get("answers", [])
            if not isinstance(answers, list) or not answers:
                return None
            ans = answers[0]
            if not isinstance(ans, dict):
                return None
            for key in ("probability", "p", "score"):
                val = ans.get(key)
                if isinstance(val, (int, float)) and 0.0 <= val <= 1.0:
                    return float(val)
            # value-style: {"value": "yes"/"no", "confidence": x}
            val = str(ans.get("value", "")).lower()
            conf = ans.get("confidence", 0.5)
            try:
                conf = float(conf)
            except (TypeError, ValueError):
                conf = 0.5
            if val in ("yes", "true", "supported", "keep"):
                return max(conf, 0.5)
            if val in ("no", "false", "unsupported", "drop"):
                return min(1.0 - conf, 0.5)
            return None
        except Exception:
            return None

    def verify(self, title: str, detail: str = "", evidence: str = "",
               ) -> ExternalVerdict | None:
        """Ask Jev. Returns verdict, or None on abstain (fail open)."""
        if not self.available():
            return None
        import httpx
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/v1/systemone",
                    headers={"Authorization": f"Bearer {self.api_key}",
                             "Content-Type": "application/json"},
                    json=self._question_payload(title, detail, evidence))
            if resp.status_code in (401, 403):
                return None  # bad key — abstain, don't launder into a verdict
            if resp.status_code != 200:
                return None
            prob = self._extract_probability(resp.json())
        except Exception:
            return None
        if prob is None:
            return None
        if prob >= KEEP_AT:
            return ExternalVerdict(True, prob, {})
        if prob <= DROP_AT:
            return ExternalVerdict(False, prob, {})
        return None  # abstain zone — caller fails open
