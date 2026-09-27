import asyncio
import re
from truthzero.tools.base import BaseTool, ToolResult


class JSAnalysisTool(BaseTool):
    name = "js_analyze"
    description = "Analyze JavaScript files for endpoints, API keys, secrets, and sensitive data. Like LinkFinder + SecretFinder."
    parameters = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "URL to JS file, or local file path"},
            "mode": {"type": "string", "enum": ["all", "endpoints", "secrets", "domains"], "default": "all"},
        },
        "required": ["target"],
    }

    ENDPOINT_PATTERNS = [
        r'(?:"|\'|\`)(/[a-zA-Z0-9_\-./]+(?:\?[a-zA-Z0-9_=&]+)?)(?:"|\'|\`)',
        r'(?:"|\'|\`)(https?://[a-zA-Z0-9._\-/]+)(?:"|\'|\`)',
        r'(?:fetch|axios|XMLHttpRequest|\.ajax|\.get|\.post|\.put|\.delete)\s*\(\s*(?:"|\'|\`)([^"\'`]+)',
        r'(?:url|endpoint|api|path|route|href|src|action)\s*[:=]\s*(?:"|\'|\`)([^"\'`]+)',
    ]

    SECRET_PATTERNS = {
        "AWS Access Key": r'(?:AKIA|ABIA|ACCA)[0-9A-Z]{16}',
        "AWS Secret Key": r'(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[:=]\s*["\']?([A-Za-z0-9/+=]{40})',
        "Google API Key": r'AIza[0-9A-Za-z_-]{35}',
        "Google OAuth": r'[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com',
        "GitHub Token": r'(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,255}',
        "Slack Token": r'xox[baprs]-[0-9a-zA-Z]{10,250}',
        "Slack Webhook": r'https://hooks\.slack\.com/services/T[A-Z0-9]{8}/B[A-Z0-9]{8}/[A-Za-z0-9]{24}',
        "Stripe Key": r'(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{24,}',
        "JWT Token": r'eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+',
        "Private Key": r'-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----',
        "Bearer Token": r'[Bb]earer\s+[A-Za-z0-9\-._~+/]+=*',
        "Basic Auth": r'[Bb]asic\s+[A-Za-z0-9+/]{10,}={0,2}',
        "Generic API Key": r'(?:api[_-]?key|apikey|API_KEY)\s*[:=]\s*["\']?([A-Za-z0-9_\-]{16,})',
        "Generic Secret": r'(?:secret|password|passwd|pwd|token|auth)\s*[:=]\s*["\']([^"\']{8,})["\']',
        "Firebase URL": r'https://[a-z0-9-]+\.firebaseio\.com',
        "S3 Bucket": r'(?:https?://)?[a-z0-9.-]+\.s3[.-](?:us|eu|ap|sa|ca|me|af)-?[a-z]*-?\d*\.amazonaws\.com',
        "Internal IP": r'(?:https?://)?(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})',
    }

    DOMAIN_PATTERN = r'(?:https?://)?(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}'

    async def execute(self, target: str = "", mode: str = "all", **kwargs) -> ToolResult:
        try:
            content = await self._fetch_content(target)
            if not content:
                return ToolResult(output="", success=False, error=f"Could not fetch content from {target}")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

        results = []

        if mode in ("all", "endpoints"):
            endpoints = self._extract_endpoints(content)
            if endpoints:
                results.append(f"ENDPOINTS ({len(endpoints)}):")
                for ep in sorted(set(endpoints))[:100]:
                    results.append(f"  {ep}")
                results.append("")

        if mode in ("all", "secrets"):
            secrets = self._extract_secrets(content)
            if secrets:
                results.append(f"SECRETS ({len(secrets)}):")
                for sec_type, values in secrets.items():
                    for val in values[:5]:
                        display = val if len(val) <= 60 else val[:57] + "..."
                        results.append(f"  [{sec_type}] {display}")
                results.append("")

        if mode in ("all", "domains"):
            domains = self._extract_domains(content)
            if domains:
                results.append(f"DOMAINS ({len(domains)}):")
                for d in sorted(domains)[:50]:
                    results.append(f"  {d}")

        if not results:
            return ToolResult(output="No findings in this JS file.", success=True)

        return ToolResult(output="\n".join(results), success=True)

    async def _fetch_content(self, target: str) -> str:
        if target.startswith(("http://", "https://")):
            import httpx
            async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
                resp = await client.get(target)
                return resp.text
        else:
            from pathlib import Path
            p = Path(target).expanduser()
            if p.exists():
                return p.read_text(errors="ignore")
        return ""

    def _extract_endpoints(self, content: str) -> list[str]:
        endpoints = []
        for pattern in self.ENDPOINT_PATTERNS:
            for match in re.finditer(pattern, content):
                ep = match.group(1) if match.lastindex else match.group(0)
                ep = ep.strip("\"'`")
                if ep and len(ep) > 1 and not ep.endswith(('.js', '.css', '.png', '.jpg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot')):
                    endpoints.append(ep)
        return endpoints

    def _extract_secrets(self, content: str) -> dict[str, list[str]]:
        secrets = {}
        for name, pattern in self.SECRET_PATTERNS.items():
            matches = re.findall(pattern, content)
            if matches:
                secrets[name] = list(set(matches))[:10]
        return secrets

    def _extract_domains(self, content: str) -> set[str]:
        domains = set()
        for match in re.finditer(self.DOMAIN_PATTERN, content):
            domain = match.group(0).lower()
            if not domain.endswith(('.js', '.css', '.png', '.jpg')):
                domain = re.sub(r'^https?://', '', domain)
                domains.add(domain.split('/')[0])
        return domains
