WORKFLOWS = {
    "full-recon": {
        "name": "Full Reconnaissance",
        "description": "Complete recon pipeline: subdomains → alive check → port scan → tech detect → dir fuzz → JS analysis",
        "steps": [
            "Enumerate subdomains for {target} using all available sources",
            "Check which discovered subdomains are alive and responding",
            "Port scan the top 1000 ports on all alive hosts",
            "Detect technology stack on all alive web servers",
            "Run directory fuzzing on all discovered web servers with common wordlists",
            "Find and analyze all JavaScript files for endpoints and secrets",
            "Generate a summary report of all findings",
        ],
    },
    "quick-recon": {
        "name": "Quick Recon",
        "description": "Fast recon: subdomains → alive → tech detect",
        "steps": [
            "Enumerate subdomains for {target}",
            "Check which subdomains are alive",
            "Detect tech stack on alive hosts",
            "Summarize findings",
        ],
    },
    "vuln-scan": {
        "name": "Vulnerability Scan",
        "description": "Automated vuln scanning: nuclei (all severities) → analyze results",
        "steps": [
            "Update nuclei templates to latest version",
            "Run nuclei scan on {target} with all severity levels",
            "Analyze and prioritize the findings by severity",
            "Generate a vulnerability report",
        ],
    },
    "xss-hunt": {
        "name": "XSS Hunting",
        "description": "Systematic XSS testing: crawl → find params → test reflections → fuzz payloads",
        "steps": [
            "Crawl {target} to discover all pages and endpoints",
            "Identify all URL parameters and form inputs that reflect user input",
            "Test each reflection point with basic XSS probes (<script>alert(1)</script>, <img src=x onerror=alert(1)>)",
            "For any that show partial reflection, try WAF bypass payloads",
            "Attempt to escalate any confirmed XSS to demonstrate session hijacking impact",
            "Document findings with PoC",
        ],
    },
    "api-hunt": {
        "name": "API Security Audit",
        "description": "API testing: discover endpoints → test auth → BOLA/IDOR → injection",
        "steps": [
            "Discover API endpoints on {target} (check /api, /v1, /v2, swagger.json, graphql)",
            "Test each endpoint without authentication headers",
            "Test for BOLA/IDOR by swapping user IDs and UUIDs across endpoints",
            "Test for mass assignment by adding extra fields (role, is_admin) to POST/PUT requests",
            "Test for SQL injection and NoSQL injection in all parameters",
            "Check rate limiting on authentication endpoints",
            "Document all findings",
        ],
    },
    "auth-test": {
        "name": "Authentication Testing",
        "description": "Test auth mechanisms: default creds → reset flow → MFA → session management",
        "steps": [
            "Test for default credentials on {target} login page",
            "Analyze the password reset flow for host header injection and token predictability",
            "Test MFA implementation for bypass: response manipulation, step skipping, OTP brute force",
            "Check session management: cookie flags, expiry, concurrent sessions, invalidation on password change",
            "Test for account enumeration via login error messages and timing differences",
            "Check JWT tokens if used: algorithm confusion, signature bypass, token expiry",
            "Document findings",
        ],
    },
    "js-recon": {
        "name": "JavaScript Analysis",
        "description": "Deep JS analysis: find all JS → extract endpoints → find secrets → map API surface",
        "steps": [
            "Crawl {target} and collect all JavaScript file URLs",
            "Download and analyze each JS file for API endpoints",
            "Search all JS files for hardcoded secrets, API keys, and tokens",
            "Extract all domains and subdomains referenced in JS",
            "Map the internal API surface from extracted endpoints",
            "Check source maps (.js.map) for original source code exposure",
            "Summarize the attack surface discovered from JS analysis",
        ],
    },
    "subdomain-takeover": {
        "name": "Subdomain Takeover Check",
        "description": "Check for subdomain takeover: enum → CNAME check → dangling records → claim",
        "steps": [
            "Enumerate all subdomains for {target}",
            "Check DNS records (CNAME, A, AAAA) for each subdomain",
            "Identify subdomains pointing to external services (AWS, Azure, GitHub Pages, Heroku, etc.)",
            "Check if any CNAME targets are unclaimed or return errors",
            "Test for potential takeover on identified dangling records",
            "Document any confirmed or potential takeover findings",
        ],
    },
}


class WorkflowRunner:
    def __init__(self, agent=None):
        self.agent = agent

    def list_workflows(self) -> list[dict]:
        return [{"key": k, "name": v["name"], "description": v["description"], "steps": len(v["steps"])} for k, v in WORKFLOWS.items()]

    def get_workflow(self, name: str) -> dict | None:
        return WORKFLOWS.get(name)

    async def run(self, workflow_name: str, target: str) -> str:
        wf = WORKFLOWS.get(workflow_name)
        if not wf:
            return f"Unknown workflow: {workflow_name}"
        if not self.agent:
            return "Agent not initialized"

        results = []
        results.append(f"Running workflow: {wf['name']}")
        results.append(f"Target: {target}")
        results.append(f"Steps: {len(wf['steps'])}")
        results.append("")

        for i, step in enumerate(wf["steps"], 1):
            prompt = step.replace("{target}", target)
            results.append(f"Step {i}/{len(wf['steps'])}: {prompt}")
            try:
                response = await self.agent.run(prompt)
                results.append(response[:500] if response else "(no output)")
            except Exception as e:
                results.append(f"Error: {e}")
            results.append("")

        results.append("Workflow complete.")
        return "\n".join(results)
