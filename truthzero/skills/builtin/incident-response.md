# Incident Response & Digital Forensics

## Evidence Collection — First Responder
```bash
# Memory acquisition (ALWAYS before disk — volatile first)
# Windows
winpmem_mini_x64.exe memdump.raw              # WinPmem memory dump
# Linux
sudo insmod lime-$(uname -r).ko "path=/evidence/memory.lime format=lime"
# Verify integrity
sha256sum memdump.raw > memdump.raw.sha256    # hash immediately after acquisition

# Disk imaging
dc3dd if=/dev/sda of=/evidence/disk.dd hash=sha256 log=/evidence/dc3dd.log  # Linux
# FTK Imager (Windows): File → Create Disk Image → Physical Drive → E01 format
# Verify
sha256sum /evidence/disk.dd                   # compare with acquisition hash

# Live triage — volatile data collection (before shutdown)
date -u && hostname && whoami                 # timestamp, system, user context
ps auxf > /evidence/processes.txt             # running processes with tree
netstat -tulnp > /evidence/network.txt        # active connections and listeners
ss -tulnp >> /evidence/network.txt            # socket statistics
cat /proc/net/arp > /evidence/arp.txt         # ARP cache
lsof -i > /evidence/open_files.txt            # open files with network
last -a > /evidence/logins.txt                # login history
cat /etc/passwd /etc/shadow > /evidence/accounts.txt  # user accounts
find / -mtime -1 -type f 2>/dev/null > /evidence/recent_files.txt  # recently modified
```

## Windows Event Log Analysis
```
CRITICAL EVENT IDS:
  4624  — Successful logon (check LogonType: 2=interactive, 3=network, 10=RDP)
  4625  — Failed logon (brute force indicator — high volume from single source)
  4648  — Explicit credential logon (RunAs, pass-the-hash)
  4688  — Process creation (with command line if audit enabled)
  4697  — Service installed (persistence)
  4698  — Scheduled task created (persistence)
  4720  — User account created (backdoor account)
  4732  — Member added to security group (privilege escalation)
  7045  — New service installed (System log — persistence)
  1102  — Audit log cleared (anti-forensics indicator)
  4104  — PowerShell ScriptBlock logging (malicious script content)
  4103  — PowerShell Module logging
```
```bash
# Chainsaw — fast Windows event log triage
chainsaw hunt /path/to/evtx/ -s sigma/ --mapping mappings/sigma-event-log-all.yml -o results.csv
chainsaw search /path/to/evtx/ -t "Event.System.EventID: 4688" --json

# Hayabusa — Windows event log fast forensics
hayabusa csv-timeline -d /path/to/evtx/ -o timeline.csv
hayabusa logon-summary -d /path/to/evtx/                # summarize logon events
hayabusa search -d /path/to/evtx/ -k "mimikatz OR sekurlsa"

# Manual PowerShell parsing
Get-WinEvent -Path .\Security.evtx -FilterXPath "*[System[EventID=4688]]" | Select TimeCreated,Message | Format-List
Get-WinEvent -Path .\Security.evtx -FilterXPath "*[System[EventID=4624] and EventData[Data[@Name='LogonType']='10']]"
```

## Memory Forensics — Volatility 3
```bash
# System information
vol3 -f memory.raw windows.info               # OS version, kernel base, DTB
vol3 -f memory.raw windows.pslist              # process list with PID, PPID, timestamps
vol3 -f memory.raw windows.pstree              # process tree — spot orphaned/suspicious parents
vol3 -f memory.raw windows.psscan              # find hidden/unlinked processes

# Network and connections
vol3 -f memory.raw windows.netscan             # TCP/UDP connections with owning PID
vol3 -f memory.raw windows.netstat             # active network connections

# Malware detection
vol3 -f memory.raw windows.malfind             # find injected code (PAGE_EXECUTE_READWRITE)
vol3 -f memory.raw windows.dlllist --pid 1234  # loaded DLLs for specific process
vol3 -f memory.raw windows.handles --pid 1234  # open handles (files, registry, mutexes)
vol3 -f memory.raw windows.cmdline             # command lines of all processes
vol3 -f memory.raw windows.svcscan             # Windows services (persistence)

# Dump artifacts
vol3 -f memory.raw windows.memmap --pid 1234 --dump  # dump process memory
vol3 -f memory.raw windows.dumpfiles --pid 1234      # dump associated files
vol3 -f memory.raw windows.hashdump            # extract password hashes (SAM)
vol3 -f memory.raw windows.cachedump           # cached domain credentials

# Linux memory
vol3 -f memory.lime linux.pslist               # Linux process list
vol3 -f memory.lime linux.bash                 # bash command history from memory
vol3 -f memory.lime linux.check_syscall        # detect syscall table hooking (rootkit)
```

## Disk Forensics
```bash
# Timeline creation with plaso
log2timeline.py /evidence/plaso.dump /evidence/disk.dd  # parse all artifacts
psort.py -o l2tcsv /evidence/plaso.dump -w /evidence/timeline.csv "date > '2025-01-01'"

# MFT analysis
analyzemft.py -f \$MFT -o mft_analysis.csv    # parse NTFS Master File Table
# Key: look for $STANDARD_INFO vs $FILE_NAME timestamp discrepancies (timestomping)

# Artifact extraction — Windows
# Prefetch: C:\Windows\Prefetch\*.pf → program execution evidence
python3 PECmd.py -d /evidence/Prefetch/ --csv /evidence/prefetch_results/
# AmCache: C:\Windows\appcompat\Programs\Amcache.hve → installed programs
python3 AmcacheParser.py -f Amcache.hve --csv /evidence/amcache_results/
# ShimCache: SYSTEM hive → executed programs
python3 ShimCacheParser.py -i SYSTEM -o shimcache.csv

# Registry analysis
regripper -r NTUSER.DAT -p all > ntuser_analysis.txt  # user activity
regripper -r SYSTEM -p all > system_analysis.txt       # services, network, USB
regripper -r SOFTWARE -p all > software_analysis.txt   # installed programs, persistence

# Browser artifacts
hindsight -i "/Users/victim/AppData/Local/Google/Chrome/User Data/Default" -o browser_report
# Extracts: history, downloads, cookies, cache, saved passwords, autofill
```

## PCAP Analysis
```bash
# Wireshark CLI (tshark)
tshark -r capture.pcap -q -z io,stat,30       # traffic statistics per 30s interval
tshark -r capture.pcap -q -z endpoints,tcp    # top talkers
tshark -r capture.pcap -q -z http,tree        # HTTP method/status breakdown
tshark -r capture.pcap -Y "dns" -T fields -e dns.qry.name | sort | uniq -c | sort -rn  # DNS queries ranked
tshark -r capture.pcap -Y "http.request" -T fields -e http.host -e http.request.uri     # HTTP requests
tshark -r capture.pcap -Y "tls.handshake.extensions_server_name" -T fields -e tls.handshake.extensions_server_name | sort -u  # SNI from TLS

# File carving from streams
tshark -r capture.pcap --export-objects http,/evidence/http_objects/  # extract HTTP transferred files
tshark -r capture.pcap --export-objects smb,/evidence/smb_objects/    # SMB file transfers

# Detect beaconing (regular interval C2 callbacks)
tshark -r capture.pcap -Y "ip.dst==SUSPECT_IP" -T fields -e frame.time_delta_displayed | sort -n
# Consistent intervals (e.g., every 60±5 seconds) = C2 beacon

# DNS tunneling detection
tshark -r capture.pcap -Y "dns.qry.name contains suspicious.domain" -T fields -e dns.qry.name
# Long subdomain labels, TXT record responses with encoded data = tunneling
```

## Recovery and Reporting
```
ROOT CAUSE ANALYSIS TEMPLATE:
1. Initial access vector: [phishing/exploit/credential/supply-chain]
2. Timeline: first compromise → detection → containment → eradication
3. Attacker TTPs mapped to MITRE ATT&CK
4. Data accessed/exfiltrated: scope and sensitivity
5. Lateral movement path: system-to-system progression
6. Persistence mechanisms found and removed
7. Detection gap: why existing controls missed the attack
8. Remediation: immediate actions taken + long-term improvements

IOC SHARING FORMAT (STIX/OpenIOC):
- File hashes (SHA256, SHA1, MD5)
- Network indicators (IPs, domains, URLs, JA3/JA3S)
- Host indicators (file paths, registry keys, services, scheduled tasks, mutexes)
- Email indicators (sender, subject, attachment hashes)
```
