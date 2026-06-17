import asyncio
import base64
import binascii
import codecs
import hashlib
import html
import json
import re
import shutil
import urllib.parse

from zer0code.tools.base import BaseTool, ToolResult

HASH_PATTERNS = [
    {"name": "MD5", "length": 32, "regex": r"^[a-fA-F0-9]{32}$", "hashcat_mode": "0", "john_format": "raw-md5"},
    {"name": "SHA-1", "length": 40, "regex": r"^[a-fA-F0-9]{40}$", "hashcat_mode": "100", "john_format": "raw-sha1"},
    {"name": "SHA-224", "length": 56, "regex": r"^[a-fA-F0-9]{56}$", "hashcat_mode": "1300", "john_format": "raw-sha224"},
    {"name": "SHA-256", "length": 64, "regex": r"^[a-fA-F0-9]{64}$", "hashcat_mode": "1400", "john_format": "raw-sha256"},
    {"name": "SHA-384", "length": 96, "regex": r"^[a-fA-F0-9]{96}$", "hashcat_mode": "10800", "john_format": "raw-sha384"},
    {"name": "SHA-512", "length": 128, "regex": r"^[a-fA-F0-9]{128}$", "hashcat_mode": "1700", "john_format": "raw-sha512"},
    {"name": "NTLM", "length": 32, "regex": r"^[a-fA-F0-9]{32}$", "hashcat_mode": "1000", "john_format": "nt"},
    {"name": "MySQL 4.1+", "length": 40, "regex": r"^\*[A-F0-9]{40}$", "hashcat_mode": "300", "john_format": "mysql-sha1"},
    {"name": "bcrypt", "length": 60, "regex": r"^\$2[aby]?\$\d{2}\$[./A-Za-z0-9]{53}$", "hashcat_mode": "3200", "john_format": "bcrypt"},
    {"name": "MD5 Crypt", "length": None, "regex": r"^\$1\$[./A-Za-z0-9]{8}\$[./A-Za-z0-9]{22}$", "hashcat_mode": "500", "john_format": "md5crypt"},
    {"name": "SHA-256 Crypt", "length": None, "regex": r"^\$5\$(rounds=\d+\$)?[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{43}$", "hashcat_mode": "7400", "john_format": "sha256crypt"},
    {"name": "SHA-512 Crypt", "length": None, "regex": r"^\$6\$(rounds=\d+\$)?[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{86}$", "hashcat_mode": "1800", "john_format": "sha512crypt"},
    {"name": "APR1 MD5", "length": None, "regex": r"^\$apr1\$[./A-Za-z0-9]{8}\$[./A-Za-z0-9]{22}$", "hashcat_mode": "1600", "john_format": "md5apr1"},
    {"name": "Argon2", "length": None, "regex": r"^\$argon2(id?|d)\$", "hashcat_mode": None, "john_format": "argon2"},
    {"name": "scrypt", "length": None, "regex": r"^\$scrypt\$", "hashcat_mode": None, "john_format": "scrypt"},
    {"name": "PBKDF2-SHA256", "length": None, "regex": r"^pbkdf2_sha256\$", "hashcat_mode": "10000", "john_format": "pbkdf2-hmac-sha256"},
    {"name": "Django PBKDF2", "length": None, "regex": r"^pbkdf2_sha256\$\d+\$", "hashcat_mode": "10000", "john_format": "django"},
    {"name": "CRC32", "length": 8, "regex": r"^[a-fA-F0-9]{8}$", "hashcat_mode": None, "john_format": None},
    {"name": "LM Hash", "length": 32, "regex": r"^[A-Fa-f0-9]{32}$", "hashcat_mode": "3000", "john_format": "lm"},
    {"name": "Kerberos 5 TGS-REP", "length": None, "regex": r"^\$krb5tgs\$", "hashcat_mode": "13100", "john_format": "krb5tgs"},
    {"name": "Kerberos 5 AS-REP", "length": None, "regex": r"^\$krb5asrep\$", "hashcat_mode": "18200", "john_format": "krb5asrep"},
    {"name": "Net-NTLMv2", "length": None, "regex": r"^[^:]+::\S+:[a-fA-F0-9]{16}:[a-fA-F0-9]{32}:[a-fA-F0-9]+$", "hashcat_mode": "5600", "john_format": "netntlmv2"},
    {"name": "Net-NTLMv1", "length": None, "regex": r"^[^:]+::\S+:[a-fA-F0-9]{16}:[a-fA-F0-9]{48}$", "hashcat_mode": "5500", "john_format": "netntlm"},
]

COMMON_PASSWORDS = [
    "password", "123456", "12345678", "qwerty", "abc123", "monkey", "1234567",
    "letmein", "trustno1", "dragon", "baseball", "iloveyou", "master",
    "sunshine", "ashley", "bailey", "passw0rd", "shadow", "123123", "654321",
    "superman", "qazwsx", "michael", "football", "password1", "password123",
    "batman", "login", "admin", "admin123", "root", "toor", "pass",
    "test", "guest", "changeme", "welcome", "welcome1", "p@ssw0rd",
    "P@ssw0rd", "P@ssword1", "Password1", "Password123", "hunter2",
    "charlie", "donald", "1234", "12345", "123456789", "1234567890",
    "secret", "love", "princess", "rockyou", "nicole", "daniel",
    "soccer", "thomas", "ranger", "buster", "robert", "jordan",
    "asshole", "pepper", "access", "hello", "thunder", "fuck",
    "summer", "1q2w3e4r", "qwerty123", "solo", "loveme", "computer",
    "starwars", "whatever", "matrix", "cheese", "121212", "winter",
    "dallas", "hammer", "george", "harley", "222222", "purple",
]


class HashIdentifyTool(BaseTool):
    name = "hash_identify"
    description = "Identify the type of a hash based on its format, length, and character patterns"
    parameters = {
        "type": "object",
        "properties": {
            "hash_value": {
                "type": "string",
                "description": "The hash value to identify",
            },
        },
        "required": ["hash_value"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        hash_value = kwargs.get("hash_value", "").strip()

        if not hash_value:
            return ToolResult(output="", success=False, error="No hash value provided")

        matches = []
        for pattern in HASH_PATTERNS:
            if re.match(pattern["regex"], hash_value):
                matches.append(pattern)

        output_lines = [
            f"[Hash Identification]",
            f"Input: {hash_value}",
            f"Length: {len(hash_value)}",
            "",
        ]

        if matches:
            output_lines.append(f"Possible types ({len(matches)}):")
            output_lines.append("")
            for m in matches:
                output_lines.append(f"  Type: {m['name']}")
                if m["hashcat_mode"]:
                    output_lines.append(f"    Hashcat mode: -m {m['hashcat_mode']}")
                if m["john_format"]:
                    output_lines.append(f"    John format: --format={m['john_format']}")
                output_lines.append("")

            if len(matches) > 1 and len(hash_value) == 32:
                output_lines.append("Note: 32-char hex could be MD5, NTLM, or LM. Context determines actual type.")
                output_lines.append("  - NTLM: Windows password hash")
                output_lines.append("  - MD5: General purpose / Linux")
                output_lines.append("  - LM: Legacy Windows (rare)")
        else:
            output_lines.append("No known hash format matched")
            output_lines.append("")
            if hash_value.startswith("$"):
                output_lines.append("Hash appears to use modular crypt format but type is not recognized")
            elif all(c in "0123456789abcdefABCDEF" for c in hash_value):
                output_lines.append(f"Hex string of length {len(hash_value)} - uncommon hash length")
            else:
                output_lines.append("May be an encoded value (base64?) rather than a hash")

        return ToolResult(output="\n".join(output_lines), success=True)


class HashCrackTool(BaseTool):
    name = "hash_crack"
    description = "Attempt to crack a hash using hashcat, john the ripper, or a built-in common password list"
    parameters = {
        "type": "object",
        "properties": {
            "hash_value": {
                "type": "string",
                "description": "The hash to crack",
            },
            "hash_type": {
                "type": "string",
                "description": "Hash type (e.g. 'md5', 'sha1', 'sha256', 'ntlm', 'bcrypt')",
            },
            "wordlist": {
                "type": "string",
                "description": "Path to wordlist file (default: rockyou.txt or built-in list)",
            },
        },
        "required": ["hash_value"],
    }

    HASHCAT_MODES = {
        "md5": "0", "sha1": "100", "sha256": "1400", "sha512": "1700",
        "ntlm": "1000", "bcrypt": "3200", "mysql": "300",
        "md5crypt": "500", "sha256crypt": "7400", "sha512crypt": "1800",
        "lm": "3000", "net-ntlmv2": "5600", "kerberoast": "13100",
        "asrep": "18200",
    }

    JOHN_FORMATS = {
        "md5": "raw-md5", "sha1": "raw-sha1", "sha256": "raw-sha256",
        "sha512": "raw-sha512", "ntlm": "nt", "bcrypt": "bcrypt",
        "mysql": "mysql-sha1", "md5crypt": "md5crypt",
        "sha256crypt": "sha256crypt", "sha512crypt": "sha512crypt",
        "lm": "lm", "net-ntlmv2": "netntlmv2", "kerberoast": "krb5tgs",
        "asrep": "krb5asrep",
    }

    HASH_FUNCS = {
        "md5": lambda p: hashlib.md5(p.encode()).hexdigest(),
        "sha1": lambda p: hashlib.sha1(p.encode()).hexdigest(),
        "sha256": lambda p: hashlib.sha256(p.encode()).hexdigest(),
        "sha512": lambda p: hashlib.sha512(p.encode()).hexdigest(),
    }

    def _detect_type(self, hash_value: str) -> str | None:
        for pattern in HASH_PATTERNS:
            if re.match(pattern["regex"], hash_value):
                name = pattern["name"].lower()
                if "md5" in name and len(hash_value) == 32:
                    return "md5"
                if "sha-1" in name:
                    return "sha1"
                if "sha-256" in name and len(hash_value) == 64:
                    return "sha256"
                if "sha-512" in name and len(hash_value) == 128:
                    return "sha512"
                if "bcrypt" in name:
                    return "bcrypt"
                if "ntlm" in name:
                    return "ntlm"
                for key in self.HASHCAT_MODES:
                    if key in name.replace("-", "").replace(" ", ""):
                        return key
        return None

    async def execute(self, **kwargs) -> ToolResult:
        hash_value = kwargs.get("hash_value", "").strip()
        hash_type = kwargs.get("hash_type", "")
        wordlist = kwargs.get("wordlist", "")

        if not hash_value:
            return ToolResult(output="", success=False, error="No hash value provided")

        if not hash_type:
            hash_type = self._detect_type(hash_value)
            if not hash_type:
                return ToolResult(
                    output="", success=False,
                    error="Could not auto-detect hash type. Please specify hash_type.",
                )

        hash_type = hash_type.lower().strip()

        if not wordlist:
            for candidate in [
                "/usr/share/wordlists/rockyou.txt",
                "/usr/share/seclists/Passwords/Leaked-Databases/rockyou.txt",
                "/opt/wordlists/rockyou.txt",
            ]:
                try:
                    with open(candidate):
                        wordlist = candidate
                        break
                except FileNotFoundError:
                    continue

        if shutil.which("hashcat") and hash_type in self.HASHCAT_MODES:
            mode = self.HASHCAT_MODES[hash_type]
            wl = wordlist if wordlist else "/usr/share/wordlists/rockyou.txt"
            try:
                proc = await asyncio.create_subprocess_exec(
                    "hashcat", "-m", mode, "-a", "0", hash_value, wl,
                    "--force", "--potfile-disable", "-O",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                output = stdout.decode("utf-8", errors="replace")

                show_proc = await asyncio.create_subprocess_exec(
                    "hashcat", "-m", mode, hash_value, "--show",
                    "--force", "--potfile-disable",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                show_out, _ = await asyncio.wait_for(show_proc.communicate(), timeout=10)
                show_str = show_out.decode("utf-8", errors="replace").strip()

                if ":" in show_str:
                    cracked = show_str.split(":", 1)[1]
                    return ToolResult(
                        output=f"[Hash Crack] SUCCESS (hashcat)\nHash: {hash_value}\nType: {hash_type}\nCracked: {cracked}",
                        success=True,
                    )

                return ToolResult(
                    output=f"[Hash Crack] Not cracked (hashcat)\nHash: {hash_value}\nType: {hash_type}\n\n{output[:2000]}",
                    success=True,
                )
            except asyncio.TimeoutError:
                return ToolResult(output="", success=False, error="hashcat timed out after 300s")
            except Exception:
                pass

        if shutil.which("john") and hash_type in self.JOHN_FORMATS:
            john_format = self.JOHN_FORMATS[hash_type]
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".hash", delete=False) as tmp:
                    tmp.write(hash_value + "\n")
                    tmp_path = tmp.name

                cmd = ["john", f"--format={john_format}", tmp_path]
                if wordlist:
                    cmd.append(f"--wordlist={wordlist}")

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)

                show_proc = await asyncio.create_subprocess_exec(
                    "john", "--show", f"--format={john_format}", tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                show_out, _ = await asyncio.wait_for(show_proc.communicate(), timeout=10)
                show_str = show_out.decode("utf-8", errors="replace").strip()

                import os
                os.unlink(tmp_path)

                for line in show_str.splitlines():
                    if ":" in line and "0 password hashes cracked" not in line:
                        cracked = line.split(":", 1)[1].split(":")[0] if ":" in line else ""
                        if cracked:
                            return ToolResult(
                                output=f"[Hash Crack] SUCCESS (john)\nHash: {hash_value}\nType: {hash_type}\nCracked: {cracked}",
                                success=True,
                            )

                return ToolResult(
                    output=f"[Hash Crack] Not cracked (john)\nHash: {hash_value}\nType: {hash_type}",
                    success=True,
                )
            except asyncio.TimeoutError:
                return ToolResult(output="", success=False, error="john timed out after 300s")
            except Exception:
                pass

        if hash_type in self.HASH_FUNCS:
            hash_func = self.HASH_FUNCS[hash_type]
            hash_lower = hash_value.lower()

            passwords = list(COMMON_PASSWORDS)
            if wordlist:
                try:
                    with open(wordlist) as f:
                        for line in f:
                            passwords.append(line.strip())
                            if len(passwords) > 100000:
                                break
                except Exception:
                    pass

            for pwd in passwords:
                if hash_func(pwd) == hash_lower:
                    return ToolResult(
                        output=f"[Hash Crack] SUCCESS (Python fallback)\nHash: {hash_value}\nType: {hash_type}\nCracked: {pwd}",
                        success=True,
                    )

            return ToolResult(
                output=f"[Hash Crack] Not cracked (Python fallback, tried {len(passwords)} passwords)\nHash: {hash_value}\nType: {hash_type}\n\nInstall hashcat or john for more comprehensive cracking.",
                success=True,
            )

        return ToolResult(
            output=f"[Hash Crack] Cannot crack type '{hash_type}' without hashcat/john\nHash: {hash_value}",
            success=False,
            error="No cracking tool available for this hash type",
        )


class EncoderDecoderTool(BaseTool):
    name = "encoder_decoder"
    description = "Encode or decode data using various formats (base64, URL, hex, HTML entities, ROT13, binary, JWT)"
    parameters = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "The string to encode or decode",
            },
            "operation": {
                "type": "string",
                "enum": ["encode", "decode"],
                "description": "Whether to encode or decode",
            },
            "type": {
                "type": "string",
                "enum": ["base64", "url", "hex", "html", "rot13", "binary", "jwt_decode"],
                "description": "Encoding/decoding format",
            },
        },
        "required": ["input", "operation", "type"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        input_str = kwargs.get("input", "")
        operation = kwargs.get("operation", "")
        enc_type = kwargs.get("type", "")

        if not input_str:
            return ToolResult(output="", success=False, error="No input provided")

        if not operation or operation not in ("encode", "decode"):
            return ToolResult(output="", success=False, error="operation must be 'encode' or 'decode'")

        if not enc_type:
            return ToolResult(output="", success=False, error="No encoding type specified")

        try:
            result = self._process(input_str, operation, enc_type)
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Processing error: {e}")

        output_lines = [
            f"[{operation.title()}] {enc_type}",
            f"Input: {input_str[:200]}{'...' if len(input_str) > 200 else ''}",
            f"Output:",
            result,
        ]

        return ToolResult(output="\n".join(output_lines), success=True)

    def _process(self, input_str: str, operation: str, enc_type: str) -> str:
        if enc_type == "base64":
            if operation == "encode":
                return base64.b64encode(input_str.encode()).decode()
            else:
                padding = 4 - len(input_str) % 4
                if padding != 4:
                    input_str += "=" * padding
                return base64.b64decode(input_str).decode("utf-8", errors="replace")

        elif enc_type == "url":
            if operation == "encode":
                return urllib.parse.quote(input_str, safe="")
            else:
                return urllib.parse.unquote(input_str)

        elif enc_type == "hex":
            if operation == "encode":
                return binascii.hexlify(input_str.encode()).decode()
            else:
                cleaned = input_str.replace("0x", "").replace(" ", "").replace("\\x", "")
                return binascii.unhexlify(cleaned).decode("utf-8", errors="replace")

        elif enc_type == "html":
            if operation == "encode":
                return html.escape(input_str)
            else:
                return html.unescape(input_str)

        elif enc_type == "rot13":
            return codecs.encode(input_str, "rot_13")

        elif enc_type == "binary":
            if operation == "encode":
                return " ".join(format(ord(c), "08b") for c in input_str)
            else:
                bits = input_str.replace(" ", "")
                chars = [bits[i:i + 8] for i in range(0, len(bits), 8)]
                return "".join(chr(int(b, 2)) for b in chars if len(b) == 8)

        elif enc_type == "jwt_decode":
            return self._decode_jwt(input_str)

        raise ValueError(f"Unknown type: {enc_type}")

    def _decode_jwt(self, token: str) -> str:
        parts = token.strip().split(".")
        if len(parts) not in (2, 3):
            raise ValueError(f"Invalid JWT: expected 2-3 parts, got {len(parts)}")

        def b64_decode_part(part: str) -> str:
            padding = 4 - len(part) % 4
            if padding != 4:
                part += "=" * padding
            decoded = base64.urlsafe_b64decode(part)
            return decoded.decode("utf-8", errors="replace")

        output_parts = []

        try:
            header_raw = b64_decode_part(parts[0])
            header = json.loads(header_raw)
            output_parts.append("=== JWT Header ===")
            output_parts.append(json.dumps(header, indent=2))
        except Exception as e:
            output_parts.append(f"=== JWT Header (raw) ===")
            output_parts.append(f"Error parsing: {e}")
            try:
                output_parts.append(b64_decode_part(parts[0]))
            except Exception:
                output_parts.append(parts[0])

        output_parts.append("")

        try:
            payload_raw = b64_decode_part(parts[1])
            payload = json.loads(payload_raw)
            output_parts.append("=== JWT Payload ===")
            output_parts.append(json.dumps(payload, indent=2))

            import time
            if "exp" in payload:
                exp_time = payload["exp"]
                try:
                    exp_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(exp_time))
                    expired = exp_time < time.time()
                    output_parts.append(f"\nExpires: {exp_str} ({'EXPIRED' if expired else 'valid'})")
                except Exception:
                    pass
            if "iat" in payload:
                try:
                    iat_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["iat"]))
                    output_parts.append(f"Issued: {iat_str}")
                except Exception:
                    pass
            if "nbf" in payload:
                try:
                    nbf_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(payload["nbf"]))
                    output_parts.append(f"Not Before: {nbf_str}")
                except Exception:
                    pass
        except Exception as e:
            output_parts.append(f"=== JWT Payload (raw) ===")
            output_parts.append(f"Error parsing: {e}")
            try:
                output_parts.append(b64_decode_part(parts[1]))
            except Exception:
                output_parts.append(parts[1])

        output_parts.append("")

        if len(parts) == 3:
            output_parts.append("=== JWT Signature ===")
            output_parts.append(parts[2])
            try:
                header = json.loads(b64_decode_part(parts[0]))
                alg = header.get("alg", "unknown")
                output_parts.append(f"Algorithm: {alg}")
                if alg.lower() == "none":
                    output_parts.append("WARNING: Algorithm is 'none' - signature not verified!")
                elif alg.startswith("HS"):
                    output_parts.append("HMAC signature - crackable with hashcat -m 16500")
            except Exception:
                pass

        return "\n".join(output_parts)
