# Bug Bounty Hunting Workflow

## Target Selection
- Prioritize programs with `managed` triage and fast response times (<24h) on HackerOne
- Filter by bounty range: skip programs paying <$100 for criticals unless building reputation
- Prefer targets with wide scope (*.target.com) over single-domain programs
- Check disclosed reports: programs with many resolved reports have responsive teams
- New programs (launched <30 days) have the highest density of unfound bugs
- Avoid programs with >500 hackers and <5 resolved reports — likely unresponsive
- Bugcrowd: sort by `Highest Reward` and filter `Ongoing` programs with VRT categories you know

## Recon Pipeline — Passive
- Subdomain enum: `subfinder -d target.com -all -o subs.txt && dnsx -l subs.txt -resp -o alive.txt`
- Certificate transparency: `curl -s "https://crt.sh/?q=%25.target.com&output=json" | jq -r '.[].name_value' | sort -u`
- Wayback URLs: `waybackurls target.com | grep -E '\.(php|asp|jsp|json|xml|config|env|bak|sql)' | sort -u`
- GitHub dorking: `site:github.com "target.com" password OR secret OR api_key OR token`
- Shodan: `shodan search "ssl.cert.subject.cn:target.com" --fields ip_str,port,org`
- JS file endpoint extraction: `katana -u https://target.com -jc -d 3 | grep -E '\.js$' | while read js; do python3 LinkFinder.py -i "$js" -o cli; done`
- Google dorks: `site:target.com filetype:pdf OR filetype:xlsx OR filetype:doc inurl:admin`

## Recon Pipeline — Active
- Port scan: `naabu -host target.com -top-ports 1000 -o ports.txt`
- Directory fuzzing: `ffuf -u https://target.com/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-large-words.txt -mc 200,301,302,403 -ac`
- Tech fingerprint: `whatweb https://target.com` and `wappalyzer` browser extension
- API discovery: `ffuf -u https://target.com/api/FUZZ -w /usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt -mc 200,401,403,405`
- Virtual host enum: `ffuf -u https://target.com -H "Host: FUZZ.target.com" -w subs.txt -fs <default_size>`
- Screenshot live hosts: `httpx -l alive.txt -screenshot -o screenshots/`

## Vulnerability Hunting Priority (by ROI)
1. IDOR on every authenticated endpoint — change IDs, UUIDs, check horizontal/vertical access
2. Authentication bypass — default creds, password reset, MFA skip, JWT manipulation
3. SSRF — any URL/webhook/callback input → test `http://169.254.169.254/latest/meta-data/`
4. Privilege escalation — change `role:user` to `role:admin` in request, test admin endpoints as user
5. Business logic — negative quantities, race conditions on payments, coupon stacking
6. XSS — stored in profiles/comments for ATO chains, not reflected with self-only impact
7. SQL injection — search fields, sort parameters, filter values, GraphQL arguments
8. File upload — bypass extension filters, upload webshells, SVG XSS, SSRF via PDF/DOCX

## Finding Validation
- IDOR: demonstrate reading another user's data or modifying their account — show two accounts
- XSS: show cookie theft or account takeover, not just `alert(1)` — use `fetch()` to exfil
- SSRF: show internal metadata read (cloud keys) or internal service access — not just DNS pingback
- SQLi: extract actual data (version, table names, user data) — not just sleep-based confirmation
- RCE: show `id && hostname` output — not just a DNS callback with no proof of execution context

## Report Writing
- Title: `[IDOR] in /api/v2/users/{id}/profile allows reading any user's PII via direct object reference`
- Include: numbered steps to reproduce with exact curl commands, two test accounts, expected vs actual
- Impact: "Attacker can read name, email, phone, address of all 2M users by iterating the numeric ID"
- CVSS: use `first.org/cvss/calculator/3.1` — be honest, don't inflate
- Attach: screenshots with timestamps, HTTP request/response pairs, video PoC for complex flows
- HackerOne: use Markdown, reference CWE, suggest remediation, be concise and professional
- Bugcrowd: match VRT category exactly, request severity override if VRT default is too low

## Common Rejection Reasons
- Theoretical impact with no PoC ("could potentially allow...") — always demonstrate
- Self-XSS or login/logout CSRF — not impactful, always rejected
- Missing rate limiting on non-sensitive endpoints — informational only
- SPF/DKIM/DMARC misconfiguration without demonstrated spoofing to internal users
- Clickjacking on pages with no state-changing actions
- Open redirect without a chain to OAuth token theft or phishing with session
- Version disclosure, directory listing, verbose errors — informational tier

## Bug Chaining Examples
- SSRF → `http://169.254.169.254/latest/meta-data/iam/security-credentials/role` → AWS keys → S3 access = Critical
- Stored XSS in profile → victim views → `fetch('/api/account/email', {method:'PUT', body:'email=attacker@evil.com'})` → ATO = Critical
- Open redirect at `/login?next=` → OAuth `redirect_uri` bypass → authorization code theft → ATO = High
- Subdomain takeover → set cookie on `.target.com` → session fixation on main app = High
- CORS misconfiguration + stored XSS on trusted origin → cross-origin data theft = High

## Platform Tips
- HackerOne: build signal by submitting to Disclosure programs first; +7 signal per valid report
- HackerOne: check `hacktivity` for disclosed reports — learn what the program accepts
- Bugcrowd: P1-P4 priority maps to Critical-Low; submissions outside VRT get auto-closed
- Both: respond to triager questions within 24h or report may be closed as unresponsive
- Collaborate: if you find half a chain, some programs allow researcher collaboration
