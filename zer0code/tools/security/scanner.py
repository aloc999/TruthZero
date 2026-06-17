import asyncio
import json
import re
import shutil

import httpx

from zer0code.tools.base import BaseTool, ToolResult


class NucleiScanTool(BaseTool):
    name = "nuclei_scan"
    description = "Run nuclei vulnerability scanner against a target with optional template and severity filters"
    parameters = {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Target URL or host to scan",
            },
            "templates": {
                "type": "string",
                "description": "Specific nuclei template or directory (e.g. 'cves/', 'exposures/')",
            },
            "severity": {
                "type": "string",
                "description": "Severity filter (critical, high, medium, low, info)",
            },
        },
        "required": ["target"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        target = kwargs.get("target", "")
        templates = kwargs.get("templates")
        severity = kwargs.get("severity")

        if not target:
            return ToolResult(output="", success=False, error="No target provided")

        if not shutil.which("nuclei"):
            return ToolResult(
                output="",
                success=False,
                error="nuclei not found. Install: go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
            )

        cmd = ["nuclei", "-u", target, "-jsonl", "-silent"]

        if templates:
            cmd.extend(["-t", templates])
        if severity:
            cmd.extend(["-s", severity])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            raw_output = stdout.decode("utf-8", errors="replace").strip()

            findings = []
            for line in raw_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    finding = json.loads(line)
                    findings.append({
                        "template": finding.get("template-id", ""),
                        "name": finding.get("info", {}).get("name", ""),
                        "severity": finding.get("info", {}).get("severity", ""),
                        "matched_at": finding.get("matched-at", ""),
                        "type": finding.get("type", ""),
                        "matcher_name": finding.get("matcher-name", ""),
                        "extracted_results": finding.get("extracted-results", []),
                    })
                except json.JSONDecodeError:
                    findings.append({"raw": line})

            output_lines = [
                f"[Nuclei Scan] {target}",
                f"Findings: {len(findings)}",
                "",
            ]

            if findings:
                for f in findings:
                    if "raw" in f:
                        output_lines.append(f["raw"])
                    else:
                        sev = f["severity"].upper() if f["severity"] else "UNKNOWN"
                        output_lines.append(f"[{sev}] {f['name']}")
                        output_lines.append(f"  Template: {f['template']}")
                        output_lines.append(f"  Matched: {f['matched_at']}")
                        if f["matcher_name"]:
                            output_lines.append(f"  Matcher: {f['matcher_name']}")
                        if f["extracted_results"]:
                            output_lines.append(f"  Extracted: {', '.join(f['extracted_results'][:5])}")
                        output_lines.append("")
            else:
                output_lines.append("No vulnerabilities found")

            stderr_str = stderr.decode("utf-8", errors="replace").strip()
            if stderr_str:
                output_lines.extend(["", "--- stderr ---", stderr_str])

            return ToolResult(output="\n".join(output_lines), success=True)

        except asyncio.TimeoutError:
            return ToolResult(output="", success=False, error="Nuclei scan timed out after 600s")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Nuclei error: {e}")


COMMON_PATHS = [
    "admin", "admin/", "administrator", "administrator/", "admin/login",
    "admin/dashboard", "api", "api/", "api/v1", "api/v2", "api/v3",
    "api/docs", "api/swagger", "api/graphql", "graphql", "graphiql",
    "login", "signin", "signup", "register", "auth", "auth/login",
    "oauth", "oauth/authorize", "dashboard", "dashboard/",
    "panel", "cpanel", "wp-admin", "wp-login.php", "wp-content",
    "wp-includes", "wp-json", "wp-json/wp/v2/users",
    ".git", ".git/config", ".git/HEAD", ".gitignore",
    ".env", ".env.local", ".env.production", ".env.backup",
    ".htaccess", ".htpasswd", ".DS_Store",
    "robots.txt", "sitemap.xml", "crossdomain.xml", "security.txt",
    ".well-known/security.txt", ".well-known/openid-configuration",
    "server-status", "server-info", "status", "health", "healthz",
    "health/live", "health/ready", "ping", "info",
    "actuator", "actuator/health", "actuator/env", "actuator/beans",
    "actuator/mappings", "actuator/heapdump", "actuator/configprops",
    "console", "debug", "trace", "elmah.axd", "phpinfo.php",
    "test", "test.php", "info.php", "phpinfo", "php_info",
    "config", "config.php", "config.yml", "config.json",
    "configuration", "settings", "setup", "install",
    "backup", "backup.sql", "backup.zip", "db.sql", "dump.sql",
    "database", "db", "phpmyadmin", "pma", "adminer", "adminer.php",
    "swagger", "swagger-ui", "swagger-ui.html", "swagger.json",
    "openapi.json", "api-docs", "redoc",
    "docs", "doc", "documentation",
    "static", "assets", "uploads", "upload", "files", "media",
    "images", "img", "css", "js", "fonts",
    "cgi-bin", "cgi-bin/", "bin",
    "tmp", "temp", "cache", "log", "logs",
    "error", "errors", "error_log", "debug.log",
    "private", "internal", "secret", "secrets",
    "dev", "development", "staging", "stage", "uat", "qa",
    "old", "new", "bak", "orig",
    "user", "users", "account", "accounts", "profile",
    "portal", "manager", "management",
    "metrics", "monitoring", "prometheus", "grafana",
    "jenkins", "ci", "build",
    "node_modules", "vendor", "composer.json", "package.json",
    "Dockerfile", "docker-compose.yml",
    ".svn", ".svn/entries", ".hg",
    "web.config", "WEB-INF", "WEB-INF/web.xml",
    "META-INF", "META-INF/MANIFEST.MF",
    "crossdomain.xml", "clientaccesspolicy.xml",
    "feed", "rss", "atom.xml",
    "xmlrpc.php", "readme.html", "license.txt", "changelog.txt",
]


class DirFuzzTool(BaseTool):
    name = "dir_fuzz"
    description = "Fuzz directories and files on a web server using ffuf, gobuster, or a built-in Python fallback"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Base URL to fuzz (e.g. https://example.com)",
            },
            "wordlist": {
                "type": "string",
                "description": "Path to wordlist file",
            },
            "extensions": {
                "type": "string",
                "description": "Comma-separated file extensions to append (e.g. 'php,html,js')",
            },
            "threads": {
                "type": "integer",
                "description": "Number of concurrent threads",
                "default": 20,
            },
        },
        "required": ["url"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "").rstrip("/")
        wordlist = kwargs.get("wordlist")
        extensions = kwargs.get("extensions", "")
        threads = kwargs.get("threads", 20)

        if not url:
            return ToolResult(output="", success=False, error="No URL provided")

        if shutil.which("ffuf") and wordlist:
            try:
                cmd = [
                    "ffuf", "-u", f"{url}/FUZZ", "-w", wordlist,
                    "-mc", "200,201,204,301,302,307,308,401,403,405,500",
                    "-t", str(threads), "-o", "/dev/stdout", "-of", "json", "-s",
                ]
                if extensions:
                    cmd.extend(["-e", ",".join(f".{e.strip('.')}" for e in extensions.split(","))])

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
                raw = stdout.decode("utf-8", errors="replace")

                try:
                    data = json.loads(raw)
                    results = data.get("results", [])
                    output_lines = [
                        f"[Directory Fuzz] {url} (ffuf)",
                        f"Found: {len(results)} results",
                        "",
                        f"{'STATUS':<10} {'SIZE':<10} {'PATH'}",
                    ]
                    for r in results:
                        output_lines.append(
                            f"{r.get('status', '?'):<10} {r.get('length', '?'):<10} /{r.get('input', {}).get('FUZZ', '?')}"
                        )
                    return ToolResult(output="\n".join(output_lines), success=True)
                except json.JSONDecodeError:
                    return ToolResult(output=raw, success=True)

            except asyncio.TimeoutError:
                return ToolResult(output="", success=False, error="ffuf timed out after 300s")
            except Exception as e:
                pass

        if shutil.which("gobuster") and wordlist:
            try:
                cmd = [
                    "gobuster", "dir", "-u", url, "-w", wordlist,
                    "-t", str(threads), "-q", "--no-progress",
                    "-s", "200,201,204,301,302,307,308,401,403,405,500",
                ]
                if extensions:
                    cmd.extend(["-x", extensions])

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
                output = stdout.decode("utf-8", errors="replace").strip()
                return ToolResult(
                    output=f"[Directory Fuzz] {url} (gobuster)\n\n{output}",
                    success=True,
                )
            except asyncio.TimeoutError:
                return ToolResult(output="", success=False, error="gobuster timed out")
            except Exception:
                pass

        paths = list(COMMON_PATHS)
        if wordlist:
            try:
                with open(wordlist) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            paths.append(line)
            except Exception:
                pass

        if extensions:
            ext_list = [e.strip().lstrip(".") for e in extensions.split(",")]
            expanded = list(paths)
            for path in paths:
                if "." not in path.split("/")[-1]:
                    for ext in ext_list:
                        expanded.append(f"{path}.{ext}")
            paths = expanded

        found = []
        sem = asyncio.Semaphore(threads)

        async def check_path(client: httpx.AsyncClient, path: str):
            async with sem:
                try:
                    full_url = f"{url}/{path}"
                    resp = await client.get(full_url, follow_redirects=False)
                    if resp.status_code in (200, 201, 204, 301, 302, 307, 308, 401, 403, 405, 500):
                        found.append({
                            "path": f"/{path}",
                            "status": resp.status_code,
                            "size": len(resp.content),
                            "redirect": resp.headers.get("location", ""),
                        })
                except Exception:
                    pass

        async with httpx.AsyncClient(
            timeout=10, verify=False, follow_redirects=False,
            limits=httpx.Limits(max_connections=threads, max_keepalive_connections=threads),
        ) as client:
            await asyncio.gather(*[check_path(client, p) for p in paths])

        found.sort(key=lambda x: (x["status"], x["path"]))

        output_lines = [
            f"[Directory Fuzz] {url} (Python fallback)",
            f"Checked: {len(paths)} paths",
            f"Found: {len(found)} results",
            "",
        ]

        if found:
            output_lines.append(f"{'STATUS':<10} {'SIZE':<10} {'PATH':<40} {'REDIRECT'}")
            for f_item in found:
                redirect = f_item["redirect"]
                redirect_str = f"-> {redirect}" if redirect else ""
                output_lines.append(
                    f"{f_item['status']:<10} {f_item['size']:<10} {f_item['path']:<40} {redirect_str}"
                )
        else:
            output_lines.append("No results found")

        return ToolResult(output="\n".join(output_lines), success=True)


class TechDetectTool(BaseTool):
    name = "tech_detect"
    description = "Detect web technologies (server, framework, CMS, CDN/WAF, language) by analyzing HTTP response headers and body"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to analyze for technology detection",
            },
        },
        "required": ["url"],
    }

    HEADER_SIGNATURES = {
        "server": {
            "Apache": ["apache"],
            "Nginx": ["nginx"],
            "IIS": ["microsoft-iis"],
            "LiteSpeed": ["litespeed"],
            "Caddy": ["caddy"],
            "Cloudflare": ["cloudflare"],
            "OpenResty": ["openresty"],
            "Gunicorn": ["gunicorn"],
            "Uvicorn": ["uvicorn"],
            "Cowboy": ["cowboy"],
            "Kestrel": ["kestrel"],
            "Tomcat": ["tomcat", "coyote"],
            "Jetty": ["jetty"],
            "Werkzeug": ["werkzeug"],
        },
        "x-powered-by": {
            "PHP": ["php"],
            "ASP.NET": ["asp.net"],
            "Express": ["express"],
            "Next.js": ["next.js"],
            "Nuxt": ["nuxt"],
            "Django": ["django"],
            "Flask": ["flask"],
            "Ruby on Rails": ["phusion passenger"],
            "Servlet": ["servlet"],
            "JBoss": ["jboss"],
            "PleskLin": ["plesk"],
        },
    }

    HEADER_DETECTIONS = {
        "x-aspnet-version": "ASP.NET",
        "x-aspnetmvc-version": "ASP.NET MVC",
        "x-drupal-cache": "Drupal",
        "x-drupal-dynamic-cache": "Drupal",
        "x-generator": None,
        "x-wordpress": "WordPress",
        "x-varnish": "Varnish Cache",
        "x-cache": None,
        "x-amz-cf-id": "Amazon CloudFront",
        "x-amz-request-id": "AWS S3",
        "x-azure-ref": "Azure CDN",
        "cf-ray": "Cloudflare",
        "cf-cache-status": "Cloudflare",
        "x-vercel-id": "Vercel",
        "x-vercel-cache": "Vercel",
        "x-netlify-request-id": "Netlify",
        "x-served-by": None,
        "x-fastly-request-id": "Fastly",
        "x-fw-hash": "Flywheel",
        "x-litespeed-cache": "LiteSpeed Cache",
        "x-sucuri-id": "Sucuri WAF",
        "x-cdn": None,
        "x-proxy-cache": None,
        "x-shopify-stage": "Shopify",
        "x-github-request-id": "GitHub Pages",
    }

    BODY_PATTERNS = [
        (r"wp-content/", "WordPress"),
        (r"wp-includes/", "WordPress"),
        (r"/wp-json/", "WordPress"),
        (r"Joomla!", "Joomla"),
        (r"/media/jui/", "Joomla"),
        (r"drupal\.settings", "Drupal"),
        (r"/sites/default/files/", "Drupal"),
        (r"shopify\.com", "Shopify"),
        (r"cdn\.shopify\.com", "Shopify"),
        (r"__next", "Next.js"),
        (r"/_next/", "Next.js"),
        (r"__nuxt", "Nuxt.js"),
        (r"/_nuxt/", "Nuxt.js"),
        (r"__gatsby", "Gatsby"),
        (r"react", "React"),
        (r"ng-version=", "Angular"),
        (r"ng-app", "AngularJS"),
        (r"vue\.js", "Vue.js"),
        (r"data-v-[a-f0-9]", "Vue.js"),
        (r"ember", "Ember.js"),
        (r"svelte", "Svelte"),
        (r"laravel", "Laravel"),
        (r"csrfmiddlewaretoken", "Django"),
        (r"__RequestVerificationToken", "ASP.NET"),
        (r"rails", "Ruby on Rails"),
        (r"phusion", "Ruby on Rails"),
        (r"cf-connecting-ip", "Cloudflare"),
        (r"akamai", "Akamai CDN"),
        (r"sucuri", "Sucuri WAF"),
        (r"squarespace", "Squarespace"),
        (r"wix\.com", "Wix"),
        (r"webflow", "Webflow"),
        (r"ghost\.io", "Ghost"),
        (r"discourse", "Discourse"),
        (r"moodle", "Moodle"),
        (r"magento", "Magento"),
        (r"prestashop", "PrestaShop"),
        (r"bootstrap", "Bootstrap CSS"),
        (r"tailwindcss", "Tailwind CSS"),
        (r"jquery", "jQuery"),
    ]

    COOKIE_PATTERNS = {
        "PHPSESSID": "PHP",
        "JSESSIONID": "Java",
        "ASP.NET_SessionId": "ASP.NET",
        "csrftoken": "Django",
        "_rails": "Ruby on Rails",
        "laravel_session": "Laravel",
        "connect.sid": "Express/Node.js",
        "XSRF-TOKEN": "Laravel/Angular",
        "wp-settings": "WordPress",
        "__cf_bm": "Cloudflare Bot Management",
        "incap_ses": "Imperva/Incapsula",
        "visid_incap": "Imperva/Incapsula",
        "ak_bmsc": "Akamai Bot Manager",
    }

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "")

        if not url:
            return ToolResult(output="", success=False, error="No URL provided")

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            async with httpx.AsyncClient(
                timeout=15, verify=False, follow_redirects=True,
                limits=httpx.Limits(max_connections=5),
            ) as client:
                resp = await client.get(url)
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Request failed: {e}")

        technologies = {}

        def add_tech(name: str, category: str, evidence: str):
            if name not in technologies:
                technologies[name] = {"category": category, "evidence": []}
            technologies[name]["evidence"].append(evidence)

        headers = {k.lower(): v for k, v in resp.headers.items()}

        for header_name, sigs in self.HEADER_SIGNATURES.items():
            value = headers.get(header_name, "").lower()
            if value:
                for tech_name, patterns in sigs.items():
                    for pattern in patterns:
                        if pattern in value:
                            cat = "Web Server" if header_name == "server" else "Framework"
                            add_tech(tech_name, cat, f"Header {header_name}: {resp.headers.get(header_name, value)}")
                            break

        for header_name, tech_name in self.HEADER_DETECTIONS.items():
            value = headers.get(header_name)
            if value:
                if tech_name:
                    cat = "CDN/WAF" if any(w in tech_name.lower() for w in ["cloud", "cdn", "cache", "waf", "fastly", "azure", "vercel", "netlify", "aws", "sucuri"]) else "Platform"
                    add_tech(tech_name, cat, f"Header {header_name}: {value}")
                elif header_name == "x-generator":
                    add_tech(value, "CMS/Generator", f"Header {header_name}: {value}")

        body = resp.text[:100000]
        body_lower = body.lower()

        for pattern, tech_name in self.BODY_PATTERNS:
            if re.search(pattern, body_lower):
                cat = "CMS" if tech_name in ("WordPress", "Joomla", "Drupal", "Shopify", "Squarespace", "Wix", "Ghost", "Magento", "PrestaShop", "Moodle", "Discourse", "Webflow") \
                    else "Framework" if tech_name in ("Next.js", "Nuxt.js", "Gatsby", "React", "Angular", "AngularJS", "Vue.js", "Ember.js", "Svelte", "Django", "Laravel", "Ruby on Rails") \
                    else "CDN/WAF" if tech_name in ("Cloudflare", "Akamai CDN", "Sucuri WAF") \
                    else "Frontend Library"
                add_tech(tech_name, cat, f"Body pattern: {pattern}")

        cookie_header = headers.get("set-cookie", "")
        for cookie_name, tech_name in self.COOKIE_PATTERNS.items():
            if cookie_name.lower() in cookie_header.lower():
                cat = "CDN/WAF" if any(w in tech_name.lower() for w in ["cloud", "imperva", "incap", "akamai"]) else "Language/Framework"
                add_tech(tech_name, cat, f"Cookie: {cookie_name}")

        csp = headers.get("content-security-policy", "")
        if csp:
            if "googleapis.com" in csp:
                add_tech("Google APIs", "Third-Party", "CSP: googleapis.com")
            if "google-analytics.com" in csp:
                add_tech("Google Analytics", "Analytics", "CSP: google-analytics.com")
            if "cloudflare.com" in csp:
                add_tech("Cloudflare", "CDN/WAF", "CSP: cloudflare.com")

        output_lines = [
            f"[Tech Detection] {url}",
            f"Status: {resp.status_code}",
            f"Technologies detected: {len(technologies)}",
            "",
        ]

        if technologies:
            by_category = {}
            for tech_name, info in technologies.items():
                cat = info["category"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append((tech_name, info["evidence"]))

            for cat in sorted(by_category.keys()):
                output_lines.append(f"[{cat}]")
                for tech_name, evidence_list in sorted(by_category[cat]):
                    output_lines.append(f"  {tech_name}")
                    for ev in evidence_list:
                        output_lines.append(f"    - {ev}")
                output_lines.append("")
        else:
            output_lines.append("No technologies detected")

        output_lines.extend([
            "--- Response Headers ---",
        ])
        for k, v in resp.headers.items():
            output_lines.append(f"  {k}: {v}")

        return ToolResult(output="\n".join(output_lines), success=True)
