# Security Report Writing

## Title Formula
- Format: `[Vuln Type] in [Feature/Endpoint] allows [Impact] via [Method]`
- Good: `[IDOR] in /api/v2/orders/{id} allows reading any user's order history via sequential ID enumeration`
- Good: `[Stored XSS] in profile bio field allows account takeover via session cookie theft`
- Bad: `XSS found` — no context, no impact, no method
- Bad: `Multiple vulnerabilities in target.com` — split into individual reports

## Severity Assessment — CVSS 3.1 Quick Reference
- **Critical (9.0-10.0)**: RCE, full database dump, admin takeover, mass PII exposure, cloud credential theft
- **High (7.0-8.9)**: arbitrary account takeover, stored XSS→ATO chain, SSRF to internal services, privilege escalation to admin
- **Medium (4.0-6.9)**: IDOR reading limited non-sensitive data, reflected XSS requiring interaction, CSRF on non-critical actions
- **Low (0.1-3.9)**: information disclosure (version, internal paths), self-XSS, CSRF on logout
- Attack Vector: Network=0.85 (remote), Adjacent=0.62, Local=0.55, Physical=0.20
- Attack Complexity: Low=0.77, High=0.44
- Privileges Required: None=0.85, Low=0.62/0.68, High=0.27/0.50
- User Interaction: None=0.85, Required=0.62
- Use calculator: `https://first.org/cvss/calculator/3.1` — never guess, always calculate

## Steps to Reproduce
- Number every step sequentially — triager must reproduce exactly
- Include target URL, HTTP method, headers, body for each request
- Use curl commands that triager can copy-paste directly:
```
curl -X POST 'https://target.com/api/users/12345/profile' \
  -H 'Authorization: Bearer <ATTACKER_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"email":"attacker@evil.com"}'
```
- Specify test accounts used: "Account A (attacker): attacker@test.com / Account B (victim): victim@test.com"
- State expected vs actual behavior: "Expected: 403 Forbidden. Actual: 200 OK with victim's profile data"
- For multi-step chains: label each step ("Step 1: Obtain CSRF token", "Step 2: Forge request")
- Include Burp request/response pairs as code blocks for complex attacks

## Impact Statement
- State what the attacker gains: "An unauthenticated attacker can read the full name, email, phone number, and billing address of any user"
- Quantify scope: "This affects all 2.3 million registered users" (use signup counter or API enumeration)
- Describe attack scenario: "Attacker iterates IDs 1-2300000, extracting PII at 100 requests/second, completing full dump in 6.4 hours"
- Business impact: "Violates GDPR Article 32, potential regulatory fine up to 4% of annual turnover"
- Differentiate read vs write vs delete: write/delete is always higher severity than read
- Chain impact: "Combined with the open redirect (Report #12345), this SSRF can steal AWS IAM credentials from the metadata service"

## Remediation Recommendations
- Be specific: "Implement server-side authorization check comparing `request.user.id` against the resource owner ID"
- Reference framework: "Use Django's `get_object_or_404(Model, pk=pk, owner=request.user)` pattern"
- For XSS: "Apply context-aware output encoding using your framework's default escaping — do not use `| safe` or `{!! !!}`"
- For SSRF: "Validate URL against allowlist of permitted domains; deny private IP ranges (10.0.0.0/8, 172.16.0.0/12, 169.254.169.254)"
- For SQLi: "Use parameterized queries exclusively — replace string concatenation with prepared statements"
- For auth: "Implement RBAC middleware that validates permissions per-endpoint, not just authentication"
- Include code snippet showing the fix when possible

## PoC Requirements by Vulnerability Type
- **IDOR**: two accounts, show request from Account A accessing Account B's data
- **XSS**: show cookie exfiltration or action-on-behalf-of-victim, not just `alert(document.domain)`
- **SSRF**: show internal service response (metadata endpoint, internal API), not just DNS pingback
- **SQLi**: extract database version, table names, or actual data — not just `sleep(5)` confirmation
- **RCE**: show `id`, `whoami`, `hostname` output — prove execution context
- **CSRF**: provide HTML page that victim visits to trigger the action — include full HTML
- **Race condition**: show duplicate resource creation or balance manipulation with timestamps
- **File upload**: show webshell execution output or XSS trigger from uploaded file

## Common Rejection Reasons
- No demonstrated impact: "XSS exists" without showing what attacker can do with it
- Theoretical bug: "if an attacker could intercept..." — prove it or don't submit
- Self-only impact: self-XSS, CSRF on login, changing your own data to unexpected values
- Informational: version disclosure, missing headers (X-Frame-Options on API), directory listing of empty dirs
- Duplicate: search disclosed reports before submitting; unique endpoints don't mean unique root cause
- Out of scope: read the policy — third-party services, sandbox/staging, social engineering are common exclusions
- Best practice: "missing rate limiting on search" — only valid on auth/OTP/password-reset endpoints
- Scanner output: submitting raw Nessus/Burp scan results without validation — always verify manually

## Evidence Capture
- Redact session cookies: replace value with `[REDACTED]` — triager doesn't need your session
- Blur PII of real users: if you accidentally access real user data, black-bar names/emails/phones
- Timestamp all screenshots: `date` command visible in terminal, or browser clock visible
- HAR files: sanitize with `jq 'del(.log.entries[].request.headers[] | select(.name | test("cookie|authorization";"i")))' file.har`
- Screen recordings: use for complex multi-step attacks — 30-60 seconds, no audio needed
- Include both request AND response in evidence — request alone doesn't prove the vulnerability

## Report Template
```markdown
## Summary
[One sentence: what, where, impact]

## Severity
[CVSS score and vector string from first.org calculator]

## Steps to Reproduce
1. Create two accounts: attacker (attacker@test.com) and victim (victim@test.com)
2. As victim, create a resource at POST /api/resource
3. As attacker, request GET /api/resource/{victim_resource_id}
4. Observe: attacker receives victim's data (see Response section below)

## Request
[curl command or HTTP request]

## Response
[relevant response body showing the vulnerability]

## Impact
[what attacker can do, who is affected, data at risk]

## Remediation
[specific fix recommendation with code example]
```

## Platform-Specific Tips
- HackerOne: use `###` headers, attach inline images, reference CWE IDs, check signal impact before submitting
- Bugcrowd: match VRT taxonomy exactly, request severity override as first paragraph if VRT underrates
- Intigriti: follow their template, include collaborator evidence for blind vulns
- All platforms: respond to triager questions within 24 hours, be professional, don't argue severity before triage
