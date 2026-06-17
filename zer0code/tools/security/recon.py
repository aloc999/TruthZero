import asyncio
import json
import shutil
import socket

import httpx

from zer0code.tools.base import BaseTool, ToolResult


class SubdomainEnumTool(BaseTool):
    name = "subdomain_enum"
    description = "Enumerate subdomains for a given domain using subfinder, amass, or crt.sh certificate transparency fallback"
    parameters = {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Target domain to enumerate subdomains for",
            },
            "wordlist": {
                "type": "string",
                "description": "Path to wordlist for DNS brute forcing",
            },
        },
        "required": ["domain"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        domain = kwargs.get("domain", "")
        wordlist = kwargs.get("wordlist")

        if not domain:
            return ToolResult(output="", success=False, error="No domain provided")

        subdomains = set()
        methods_used = []

        if shutil.which("subfinder"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "subfinder", "-d", domain, "-silent",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
                for line in stdout.decode("utf-8", errors="replace").strip().splitlines():
                    line = line.strip()
                    if line:
                        subdomains.add(line.lower())
                methods_used.append("subfinder")
            except (asyncio.TimeoutError, Exception):
                pass

        if shutil.which("amass"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "amass", "enum", "-passive", "-d", domain,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
                for line in stdout.decode("utf-8", errors="replace").strip().splitlines():
                    line = line.strip()
                    if line:
                        subdomains.add(line.lower())
                methods_used.append("amass")
            except (asyncio.TimeoutError, Exception):
                pass

        try:
            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                resp = await client.get(
                    f"https://crt.sh/?q=%.{domain}&output=json"
                )
                if resp.status_code == 200:
                    entries = resp.json()
                    for entry in entries:
                        name_value = entry.get("name_value", "")
                        for name in name_value.split("\n"):
                            name = name.strip().lower()
                            if name and "*" not in name and name.endswith(f".{domain}") or name == domain:
                                subdomains.add(name)
                    methods_used.append("crt.sh")
        except Exception:
            pass

        if wordlist and not methods_used:
            try:
                with open(wordlist) as f:
                    words = [line.strip() for line in f if line.strip()]
                methods_used.append("dns_brute")

                async def resolve_sub(sub):
                    fqdn = f"{sub}.{domain}"
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.getaddrinfo(fqdn, None)
                        return fqdn
                    except Exception:
                        return None

                sem = asyncio.Semaphore(50)

                async def limited_resolve(sub):
                    async with sem:
                        return await resolve_sub(sub)

                results = await asyncio.gather(*[limited_resolve(w) for w in words[:5000]])
                for r in results:
                    if r:
                        subdomains.add(r.lower())
            except Exception:
                pass

        if not subdomains:
            return ToolResult(
                output="No subdomains found",
                success=True,
                error=None,
            )

        sorted_subs = sorted(subdomains)
        output_lines = [
            f"[Subdomain Enumeration] {domain}",
            f"Methods: {', '.join(methods_used) if methods_used else 'none succeeded'}",
            f"Found: {len(sorted_subs)} subdomains",
            "",
        ]
        output_lines.extend(sorted_subs)

        return ToolResult(output="\n".join(output_lines), success=True)


class PortScanTool(BaseTool):
    name = "port_scan"
    description = "Scan ports on a target host using nmap or fallback Python socket scanner"
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Target IP or hostname to scan",
            },
            "ports": {
                "type": "string",
                "description": "Port specification (e.g. '80,443', '1-1000', 'top1000')",
                "default": "top1000",
            },
            "flags": {
                "type": "string",
                "description": "Additional nmap flags (e.g. '-sV -sC')",
            },
        },
        "required": ["target"],
    }

    TOP_PORTS = [
        21, 22, 23, 25, 53, 80, 110, 111, 135, 139, 143, 161, 179, 199,
        443, 445, 465, 514, 548, 554, 587, 631, 636, 993, 995, 1025,
        1080, 1099, 1433, 1434, 1521, 1723, 2049, 2121, 2222, 2375,
        2376, 3000, 3128, 3268, 3306, 3389, 3690, 4000, 4443, 4444,
        4567, 4711, 4848, 5000, 5001, 5060, 5222, 5432, 5555, 5601,
        5672, 5900, 5984, 5985, 5986, 6000, 6001, 6379, 6443, 6666,
        7001, 7002, 7070, 7443, 7474, 7547, 7777, 8000, 8001, 8008,
        8009, 8010, 8020, 8042, 8060, 8069, 8080, 8081, 8083, 8085,
        8088, 8090, 8161, 8181, 8200, 8222, 8333, 8443, 8500, 8600,
        8834, 8880, 8888, 8983, 9000, 9001, 9042, 9043, 9060, 9080,
        9090, 9091, 9100, 9200, 9300, 9389, 9443, 9500, 9999, 10000,
        10250, 10443, 11211, 11443, 15672, 16080, 17778, 20000, 27017,
        27018, 28017, 32768, 32769, 33060, 44818, 47808, 49152, 50000,
        50030, 50060, 50070, 50075, 50090, 54321, 55555, 61616,
    ]

    def _parse_ports(self, port_spec: str) -> list[int]:
        if port_spec == "top1000" or not port_spec:
            return self.TOP_PORTS

        ports = []
        for part in port_spec.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    ports.extend(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            else:
                try:
                    ports.append(int(part))
                except ValueError:
                    pass
        return sorted(set(ports)) if ports else self.TOP_PORTS

    async def execute(self, **kwargs) -> ToolResult:
        target = kwargs.get("target", "")
        ports = kwargs.get("ports", "top1000")
        flags = kwargs.get("flags", "")

        if not target:
            return ToolResult(output="", success=False, error="No target provided")

        if shutil.which("nmap"):
            try:
                cmd = ["nmap"]
                if flags:
                    cmd.extend(flags.split())
                if ports and ports != "top1000":
                    cmd.extend(["-p", ports])
                cmd.append(target)

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
                output = stdout.decode("utf-8", errors="replace")
                if stderr:
                    output += "\n" + stderr.decode("utf-8", errors="replace")
                return ToolResult(output=output.strip(), success=proc.returncode == 0)
            except asyncio.TimeoutError:
                return ToolResult(output="", success=False, error="Nmap scan timed out after 300s")
            except Exception as e:
                return ToolResult(output="", success=False, error=f"Nmap error: {e}")

        port_list = self._parse_ports(ports)
        open_ports = []
        sem = asyncio.Semaphore(200)

        async def check_port(port: int):
            async with sem:
                try:
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(target, port),
                        timeout=2,
                    )
                    writer.close()
                    await writer.wait_closed()
                    return port
                except Exception:
                    return None

        results = await asyncio.gather(*[check_port(p) for p in port_list])
        open_ports = sorted([p for p in results if p is not None])

        service_map = {
            21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
            80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc",
            139: "netbios-ssn", 143: "imap", 161: "snmp", 179: "bgp",
            443: "https", 445: "microsoft-ds", 465: "smtps", 514: "syslog",
            548: "afp", 554: "rtsp", 587: "submission", 631: "ipp",
            636: "ldaps", 993: "imaps", 995: "pop3s", 1080: "socks",
            1099: "rmiregistry", 1433: "mssql", 1521: "oracle",
            1723: "pptp", 2049: "nfs", 2375: "docker", 2376: "docker-tls",
            3000: "grafana/node", 3128: "squid", 3306: "mysql",
            3389: "rdp", 4443: "https-alt", 4444: "metasploit",
            5000: "upnp", 5432: "postgresql", 5601: "kibana",
            5672: "amqp", 5900: "vnc", 5984: "couchdb", 5985: "winrm",
            6379: "redis", 6443: "kubernetes", 7001: "weblogic",
            7474: "neo4j", 8000: "http-alt", 8008: "http-alt",
            8009: "ajp", 8042: "yarn", 8069: "odoo", 8080: "http-proxy",
            8081: "http-alt", 8088: "http-alt", 8161: "activemq",
            8443: "https-alt", 8500: "consul", 8834: "nessus",
            8888: "http-alt", 8983: "solr", 9000: "portainer",
            9001: "supervisord", 9042: "cassandra", 9090: "prometheus",
            9200: "elasticsearch", 9300: "elasticsearch", 9443: "https-alt",
            10000: "webmin", 10250: "kubelet", 11211: "memcached",
            15672: "rabbitmq-mgmt", 27017: "mongodb", 50000: "jenkins",
            61616: "activemq",
        }

        output_lines = [
            f"[Port Scan] {target} (Python socket fallback)",
            f"Scanned {len(port_list)} ports",
            f"Open ports: {len(open_ports)}",
            "",
        ]

        if open_ports:
            output_lines.append(f"{'PORT':<10} {'STATE':<10} {'SERVICE'}")
            for p in open_ports:
                svc = service_map.get(p, "unknown")
                output_lines.append(f"{p:<10} {'open':<10} {svc}")
        else:
            output_lines.append("No open ports found")

        return ToolResult(output="\n".join(output_lines), success=True)


class DnsLookupTool(BaseTool):
    name = "dns_lookup"
    description = "Perform DNS lookups for various record types (A, AAAA, MX, NS, TXT, CNAME, SOA, PTR)"
    parameters = {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "Domain name to look up",
            },
            "record_type": {
                "type": "string",
                "description": "DNS record type (A, AAAA, MX, NS, TXT, CNAME, SOA, PTR)",
                "default": "A",
            },
        },
        "required": ["domain"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        domain = kwargs.get("domain", "")
        record_type = kwargs.get("record_type", "A").upper()

        if not domain:
            return ToolResult(output="", success=False, error="No domain provided")

        valid_types = {"A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR"}
        if record_type not in valid_types:
            return ToolResult(
                output="", success=False,
                error=f"Invalid record type: {record_type}. Valid: {', '.join(sorted(valid_types))}",
            )

        if shutil.which("dig"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "dig", "+noall", "+answer", "+authority", domain, record_type,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = stdout.decode("utf-8", errors="replace").strip()
                if output:
                    return ToolResult(
                        output=f"[DNS Lookup] {domain} ({record_type})\n\n{output}",
                        success=True,
                    )
            except Exception:
                pass

        if shutil.which("nslookup"):
            try:
                proc = await asyncio.create_subprocess_exec(
                    "nslookup", f"-type={record_type}", domain,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
                output = stdout.decode("utf-8", errors="replace").strip()
                if output:
                    return ToolResult(
                        output=f"[DNS Lookup] {domain} ({record_type})\n\n{output}",
                        success=True,
                    )
            except Exception:
                pass

        if record_type in ("A", "AAAA"):
            try:
                family = socket.AF_INET if record_type == "A" else socket.AF_INET6
                loop = asyncio.get_event_loop()
                results = await loop.getaddrinfo(domain, None, family=family)
                addresses = sorted(set(r[4][0] for r in results))
                output_lines = [f"[DNS Lookup] {domain} ({record_type}) - socket fallback", ""]
                for addr in addresses:
                    output_lines.append(f"{domain}\t{record_type}\t{addr}")
                return ToolResult(output="\n".join(output_lines), success=True)
            except socket.gaierror as e:
                return ToolResult(output="", success=False, error=f"DNS resolution failed: {e}")
        else:
            return ToolResult(
                output="",
                success=False,
                error=f"No dig/nslookup available; socket fallback only supports A/AAAA records",
            )


class WhoisTool(BaseTool):
    name = "whois_lookup"
    description = "Perform WHOIS lookup on a domain or IP address and parse key registration fields"
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Domain name or IP address to look up",
            },
        },
        "required": ["target"],
    }

    PARSE_FIELDS = {
        "registrar": [
            "registrar:", "registrar name:", "sponsoring registrar:",
        ],
        "organization": [
            "org:", "organization:", "org-name:", "registrant organization:",
            "registrant org:", "orgname:",
        ],
        "creation_date": [
            "creation date:", "created:", "created on:", "registration date:",
            "domain registration date:", "registered:",
        ],
        "expiration_date": [
            "expiry date:", "expiration date:", "registry expiry date:",
            "registrar registration expiration date:", "expires:",
            "expire date:", "paid-till:",
        ],
        "updated_date": [
            "updated date:", "last updated:", "last modified:",
            "changed:", "last update:",
        ],
        "nameservers": [
            "name server:", "nameserver:", "nserver:", "ns:",
        ],
        "status": [
            "status:", "domain status:",
        ],
        "registrant_country": [
            "registrant country:", "country:",
        ],
    }

    def _parse_whois(self, raw: str) -> dict:
        parsed = {k: [] for k in self.PARSE_FIELDS}
        for line in raw.splitlines():
            line_lower = line.strip().lower()
            for field_name, prefixes in self.PARSE_FIELDS.items():
                for prefix in prefixes:
                    if line_lower.startswith(prefix):
                        value = line.strip()[len(prefix):].strip()
                        if value and value not in parsed[field_name]:
                            parsed[field_name].append(value)
                        break
        return parsed

    async def execute(self, **kwargs) -> ToolResult:
        target = kwargs.get("target", "")

        if not target:
            return ToolResult(output="", success=False, error="No target provided")

        if not shutil.which("whois"):
            return ToolResult(
                output="", success=False,
                error="whois command not found. Install with: apt install whois",
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                "whois", target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            raw = stdout.decode("utf-8", errors="replace")

            if not raw.strip():
                return ToolResult(output="", success=False, error="Empty WHOIS response")

            parsed = self._parse_whois(raw)

            output_lines = [f"[WHOIS] {target}", ""]

            field_labels = {
                "registrar": "Registrar",
                "organization": "Organization",
                "creation_date": "Created",
                "expiration_date": "Expires",
                "updated_date": "Updated",
                "nameservers": "Nameservers",
                "status": "Status",
                "registrant_country": "Country",
            }

            for field_key, label in field_labels.items():
                values = parsed.get(field_key, [])
                if values:
                    if field_key in ("nameservers", "status"):
                        output_lines.append(f"{label}:")
                        for v in values:
                            output_lines.append(f"  {v}")
                    else:
                        output_lines.append(f"{label}: {values[0]}")

            output_lines.extend(["", "--- Raw WHOIS (truncated) ---", ""])
            raw_lines = raw.strip().splitlines()
            if len(raw_lines) > 80:
                output_lines.extend(raw_lines[:80])
                output_lines.append(f"\n... [{len(raw_lines) - 80} more lines] ...")
            else:
                output_lines.extend(raw_lines)

            return ToolResult(output="\n".join(output_lines), success=True)

        except asyncio.TimeoutError:
            return ToolResult(output="", success=False, error="WHOIS lookup timed out")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"WHOIS error: {e}")
