from dataclasses import dataclass


@dataclass
class Template:
    name: str
    description: str
    prompt: str
    placeholders: list[str]


TEMPLATES: dict[str, Template] = {
    "scan-web": Template(
        name="scan-web",
        description="Comprehensive web reconnaissance",
        prompt="Perform comprehensive web recon on {target}. Enumerate subdomains, scan ports, discover endpoints, fingerprint tech stack.",
        placeholders=["target"],
    ),
    "scan-ports": Template(
        name="scan-ports",
        description="Port scanning and service enumeration",
        prompt="Run a port scan on {target}. Identify open ports, services, versions. Check for known CVEs on discovered services.",
        placeholders=["target"],
    ),
    "find-vulns": Template(
        name="find-vulns",
        description="Vulnerability discovery and testing",
        prompt="Analyze {target} for common web vulnerabilities: SQLi, XSS, SSRF, IDOR, auth bypass. Test each systematically.",
        placeholders=["target"],
    ),
    "audit-code": Template(
        name="audit-code",
        description="Security source code audit",
        prompt="Security audit the source code at {target}. Look for injection points, hardcoded secrets, insecure deserialization, auth flaws.",
        placeholders=["target"],
    ),
    "crack-hash": Template(
        name="crack-hash",
        description="Hash identification and cracking",
        prompt="Identify and attempt to crack this hash: {input}",
        placeholders=["input"],
    ),
    "generate-report": Template(
        name="generate-report",
        description="Penetration test report generation",
        prompt="Generate a professional penetration test report for the findings in this session. Include executive summary, methodology, findings with severity, and remediation.",
        placeholders=[],
    ),
    "exploit-cve": Template(
        name="exploit-cve",
        description="CVE research and PoC generation",
        prompt="Research CVE-{input} and determine if it affects the target. Generate a safe PoC if applicable.",
        placeholders=["input"],
    ),
    "enum-subdomains": Template(
        name="enum-subdomains",
        description="Subdomain enumeration",
        prompt="Enumerate all subdomains for {target} using multiple sources. Check each for availability and interesting services.",
        placeholders=["target"],
    ),
    "test-auth": Template(
        name="test-auth",
        description="Authentication mechanism testing",
        prompt="Test the authentication mechanism at {target} for weaknesses: default creds, brute force, MFA bypass, session management.",
        placeholders=["target"],
    ),
    "test-api": Template(
        name="test-api",
        description="API security testing",
        prompt="Test the API at {target} for security issues: BOLA/IDOR, mass assignment, rate limiting, auth bypass, injection.",
        placeholders=["target"],
    ),
    "privesc-check": Template(
        name="privesc-check",
        description="Privilege escalation enumeration",
        prompt="Check the current system for privilege escalation vectors. Run enumeration and suggest attack paths.",
        placeholders=[],
    ),
    "reverse-shell": Template(
        name="reverse-shell",
        description="Reverse shell payload generation",
        prompt="Generate reverse shell payloads for {target} on port {input}. Include bash, python, php, and powershell variants.",
        placeholders=["target", "input"],
    ),
    "decode": Template(
        name="decode",
        description="String decoding and analysis",
        prompt="Decode/analyze this string: {input}. Try base64, URL encoding, JWT, hex, and other common encodings.",
        placeholders=["input"],
    ),
    "osint": Template(
        name="osint",
        description="Open-source intelligence gathering",
        prompt="Gather OSINT on {target}. Search for exposed data, leaked credentials, public repos, employee information.",
        placeholders=["target"],
    ),
    "write-exploit": Template(
        name="write-exploit",
        description="Exploit development",
        prompt="Write an exploit for the vulnerability: {input}. Include explanation and safe PoC.",
        placeholders=["input"],
    ),
}


class TemplateManager:
    def __init__(self):
        self._templates = dict(TEMPLATES)

    def get_template(self, name: str) -> dict:
        if name not in self._templates:
            raise KeyError(f"Unknown template: {name}")
        t = self._templates[name]
        return {
            "name": t.name,
            "description": t.description,
            "prompt": t.prompt,
            "placeholders": t.placeholders,
        }

    def list_templates(self) -> list[tuple[str, str]]:
        return [(t.name, t.description) for t in self._templates.values()]

    def render(self, name: str, **kwargs: str) -> str:
        if name not in self._templates:
            return ""
        t = self._templates[name]
        prompt = t.prompt
        for key, value in kwargs.items():
            prompt = prompt.replace(f"{{{key}}}", value)
        unfilled = [p for p in t.placeholders if f"{{{p}}}" in prompt]
        if unfilled:
            raise ValueError(f"Missing placeholders: {', '.join(unfilled)}")
        return prompt

    def search(self, query: str) -> list[dict]:
        query_lower = query.lower()
        results = []
        for t in self._templates.values():
            if (
                query_lower in t.name.lower()
                or query_lower in t.description.lower()
                or query_lower in t.prompt.lower()
            ):
                results.append({
                    "name": t.name,
                    "description": t.description,
                    "prompt": t.prompt,
                    "placeholders": t.placeholders,
                })
        return results

    def add_template(self, name: str, description: str, prompt: str, placeholders: list[str] = None) -> None:
        self._templates[name] = Template(
            name=name,
            description=description,
            prompt=prompt,
            placeholders=placeholders or [],
        )
