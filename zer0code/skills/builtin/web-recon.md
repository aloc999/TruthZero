# Web Application Reconnaissance

Comprehensive web recon methodology for mapping the attack surface.

## Phase 1: Passive Reconnaissance
- Certificate Transparency: `curl -s "https://crt.sh/?q=%25.TARGET&output=json" | jq -r '.[].name_value' | sort -u`
- Wayback URLs: `waybackurls TARGET | sort -u | tee wayback.txt`
- Google dorks: `site:TARGET filetype:pdf|doc|xls|conf|env|log|sql|bak`
- GitHub dorks: `"TARGET" password|secret|key|token|api_key`
- Shodan: `ssl.cert.subject.cn:TARGET`

## Phase 2: Subdomain Enumeration
- subfinder: `subfinder -d TARGET -all -o subs.txt`
- amass: `amass enum -d TARGET -passive -o amass.txt`
- DNS brute: `ffuf -u https://FUZZ.TARGET -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -mc 200,301,302,403`
- Resolve: `cat subs.txt | dnsx -a -resp -o resolved.txt`
- Alive check: `cat resolved.txt | httpx -status-code -title -tech-detect -o alive.txt`

## Phase 3: Content Discovery
- Directory fuzz: `ffuf -u https://TARGET/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt -mc 200,301,302,403 -fc 404`
- Extension fuzz: `ffuf -u https://TARGET/FUZZ -w wordlist.txt -e .php,.asp,.aspx,.jsp,.py,.rb,.bak,.old,.conf,.env,.json,.xml,.yml,.txt,.log,.sql,.zip,.tar.gz`
- API discovery: `ffuf -u https://TARGET/FUZZ -w /usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt`
- JS file extraction: `katana -u https://TARGET -jc -d 3 | grep "\.js$" | sort -u`
- JS endpoint extraction: `cat js_files.txt | while read url; do curl -s "$url" | grep -oP '"(/[a-zA-Z0-9_/\-\.]+)"' ; done | sort -u`

## Phase 4: Technology Fingerprinting
- Wappalyzer/httpx: `httpx -u TARGET -tech-detect -status-code -title -server -cdn`
- Headers: Check X-Powered-By, Server, X-AspNet-Version, X-Generator
- Error pages: Trigger 404/500 errors to identify framework (Rails, Django, Spring, Laravel)
- Cookies: Session cookie names reveal framework (PHPSESSID=PHP, JSESSIONID=Java, connect.sid=Express)
- Source comments: View source for generator tags, framework signatures, debug info

## Phase 5: Input Vector Mapping
- Map all forms, URL parameters, headers that accept user input
- Identify file upload endpoints
- Find WebSocket connections
- Locate API endpoints accepting JSON/XML
- Check for GraphQL endpoints (/graphql, /gql, /api/graphql)

## Key Files to Check
```
/.git/HEAD
/.env
/robots.txt
/sitemap.xml
/.well-known/security.txt
/server-status
/server-info
/wp-json/wp/v2/users
/api/swagger.json
/api-docs
/.DS_Store
/crossdomain.xml
/clientaccesspolicy.xml
```

## Tips
- Always run passive recon BEFORE active scanning
- Screenshot all discovered hosts: `gowitness file -f alive.txt`
- Check for subdomain takeover: CNAME pointing to unclaimed services
- JavaScript files are goldmines — extract endpoints, API keys, secrets
- Check response headers for security misconfigurations (missing CSP, HSTS, X-Frame-Options)
