# Open Source Intelligence (OSINT)

## Domain Intelligence
```bash
# WHOIS current and historical
whois target.com                              # registrar, dates, nameservers, registrant
# whoisxml API for historical: https://whois-history.whoisxmlapi.com/api/v1?domainName=target.com

# DNS — all record types
dig target.com ANY +noall +answer             # all records (if server allows)
dig target.com A AAAA MX NS TXT SOA CNAME +short  # explicit enumeration
dig @8.8.8.8 target.com TXT                   # TXT for SPF, DKIM, DMARC, verification tokens
dig -x 93.184.216.34                          # reverse DNS
host -t axfr target.com ns1.target.com        # attempt zone transfer

# Certificate transparency — subdomain discovery
curl -s "https://crt.sh/?q=%25.target.com&output=json" | jq -r '.[].name_value' | sort -u
# SecurityTrails API
curl -s "https://api.securitytrails.com/v1/domain/target.com/subdomains" -H "APIKEY: $ST_KEY" | jq '.subdomains[]'

# Subdomain enumeration — multi-tool
subfinder -d target.com -all -o subs.txt      # passive sources
amass enum -passive -d target.com -o amass.txt  # OWASP Amass passive
cat subs.txt amass.txt | sort -u > all_subs.txt
httpx -l all_subs.txt -sc -cl -title -td -o live_subs.txt  # probe live hosts

# Historical snapshots
wayback_machine_downloader target.com         # download all archived pages
echo target.com | waybackurls | sort -u       # extract all archived URLs
echo target.com | gau --threads 5             # GetAllURLs from multiple archives
```

## Infrastructure Reconnaissance
```bash
# Shodan queries
shodan search "ssl.cert.subject.cn:target.com" --fields ip_str,port,org,hostnames
shodan search "http.title:target" --fields ip_str,port,product
shodan search "org:\"Target Corp\"" --fields ip_str,port,product,hostnames
shodan host 93.184.216.34                     # all ports/services on IP

# Censys
censys search "services.tls.certificates.leaf.names: target.com"
censys search "services.http.response.body: \"target.com\""

# ASN and BGP
whois -h whois.radb.net -- "-i origin AS12345" | grep route  # prefixes for ASN
curl -s "https://api.bgpview.io/asn/12345/prefixes" | jq '.data.ipv4_prefixes[].prefix'
# Map org to ASN
curl -s "https://api.bgpview.io/search?query_term=Target+Corp" | jq '.data.asns[]'

# Cloud IP identification
curl -s https://ip-ranges.amazonaws.com/ip-ranges.json | jq -r '.prefixes[] | select(.ip_prefix | startswith("93.184"))' 
# Also check: Azure, GCP, Cloudflare IP ranges
nslookup target.com | grep -E "(cloudfront|amazonaws|azure|googleusercontent|fastly)"
```

## Organization Intelligence
```bash
# Google dorks for documents and exposure
site:target.com filetype:pdf                  # public PDFs
site:target.com filetype:xlsx OR filetype:docx OR filetype:pptx  # office docs
site:target.com inurl:admin OR inurl:login OR inurl:dashboard
site:target.com intext:"password" OR intext:"api_key" OR intext:"secret"
site:target.com ext:xml OR ext:json OR ext:yaml OR ext:env OR ext:conf
"target.com" inurl:pastebin OR inurl:trello OR inurl:jira

# Email format discovery
curl -s "https://api.hunter.io/v2/domain-search?domain=target.com&api_key=$HUNTER_KEY" | jq '.data.pattern'
# Common patterns: {first}.{last}, {f}{last}, {first}_{last}
theHarvester -d target.com -b all             # emails, hosts, names from all sources

# LinkedIn employee intelligence
# Manual: linkedin.com/company/target/people → filter by department
# Job postings reveal tech stack: "Experience with Kubernetes, AWS, React, PostgreSQL"

# Document metadata
exiftool downloaded_report.pdf                # author, software, GPS, dates, creator
exiftool -a -u -g1 *.pdf | grep -i "author\|creator\|software\|company"
```

## Code Exposure
```bash
# GitHub reconnaissance
# Org repos: github.com/orgs/target/repositories → sort by recently updated
gh search repos --owner target-org --json name,description,updatedAt
gh search code "target.com password" --json path,repository
gh search code "target.com" "api_key\|secret\|password\|token" --json path,repository

# Secret scanning
trufflehog github --org target-org            # scan entire GitHub org for secrets
trufflehog git https://github.com/target/repo.git --only-verified  # verified secrets only
gitleaks detect --source /path/to/repo -v     # local repo secret scan

# Postman public workspaces
# Search: postman.com/search?q=target.com&type=workspace
# Look for: API keys, auth tokens, internal endpoints in environment variables

# NPM/PyPI package analysis
npm info @target/package-name                 # check for internal package names
pip index versions target-internal 2>&1       # check if internal package leaked
# Search: npmjs.com/search?q=target, pypi.org/search/?q=target
```

## People Intelligence
```bash
# Email verification
curl -s "https://api.hunter.io/v2/email-verifier?email=john@target.com&api_key=$KEY" | jq '.data.status'

# Breach credential lookup (authorized use only)
# HaveIBeenPwned API
curl -s "https://haveibeenpwned.com/api/v3/breachedaccount/user@target.com" -H "hibp-api-key: $HIBP_KEY"
# DeHashed, IntelligenceX for credential pairs

# Image metadata and reverse search
exiftool photo.jpg                            # GPS coordinates, camera model, timestamp
# Google Lens, TinEye, Yandex Images for reverse image search

# Social media OSINT
# Twitter advanced: from:username since:2024-01-01 until:2024-06-01
# Instagram: check tagged locations, stories highlights, following list
# GitHub: user's repos, starred repos, commit emails in git log
git log --format="%ae" | sort -u              # extract all committer emails from repo
```

## Threat Intelligence
```bash
# Domain/IP reputation
curl -s "https://www.virustotal.com/api/v3/domains/target.com" -H "x-apikey: $VT_KEY" | jq '.data.attributes.last_analysis_stats'
curl -s "https://urlhaus-api.abuse.ch/v1/host/" -d "host=target.com"
# AlienVault OTX: otx.alienvault.com/api/v1/indicators/domain/target.com/general

# Certificate transparency monitoring
certspotter_api="https://api.certspotter.com/v1/issuances?domain=target.com&include_subdomains=true&expand=dns_names"
curl -s "$certspotter_api" | jq '.[].dns_names[]' | sort -u

# Aggregate recon output
echo "=== RECON SUMMARY ==="
echo "Subdomains: $(wc -l < all_subs.txt)"
echo "Live hosts: $(wc -l < live_subs.txt)"
echo "Emails found: $(wc -l < emails.txt)"
echo "GitHub repos: $(gh search repos --owner target-org --json name | jq length)"
echo "Open ports (Shodan): review shodan_results.json"
```
