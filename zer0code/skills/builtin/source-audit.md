# Source Code Security Audit

## SQL Injection Sinks
- Python: `cursor.execute(f"SELECT * FROM users WHERE id={user_input}")` — use parameterized queries
- PHP: `mysqli_query($conn, "SELECT * FROM users WHERE id=" . $_GET['id'])` — use prepared statements
- Java: `stmt.executeQuery("SELECT * FROM users WHERE id=" + request.getParameter("id"))`
- Node: `db.query("SELECT * FROM users WHERE id=" + req.params.id)` — use `db.query("... WHERE id=$1", [id])`
- Ruby: `User.where("name = '#{params[:name]}'")` — use `User.where(name: params[:name])`
- Grep: `grep -rnE '(execute|query|raw|where)\s*\(.*(\$_|req\.|request\.|params|user_input|f")' --include='*.py' --include='*.php' --include='*.java' --include='*.js' --include='*.rb' .`

## Command Injection Sinks
- Python: `os.system(f"ping {host}")`, `subprocess.call(cmd, shell=True)`, `eval()`, `exec()`
- PHP: `system($_GET['cmd'])`, `exec()`, `passthru()`, `shell_exec()`, `popen()`, backtick operator
- Java: `Runtime.getRuntime().exec(userInput)`, `ProcessBuilder` with unsanitized args
- Node: `child_process.exec("ls " + userDir)`, `eval(userInput)`, `vm.runInNewContext(code)`
- Ruby: `system(params[:cmd])`, `IO.popen()`, backtick, `Kernel.send(params[:method])`
- Grep: `grep -rnE '(system|exec|popen|subprocess|eval|child_process\.exec|Runtime\.exec)\s*\(' --include='*.py' --include='*.php' --include='*.java' --include='*.js' --include='*.rb' .`

## XSS / Template Injection Sinks
- Python Jinja2: `{{ user_input | safe }}` or `Markup(user_input)` disables autoescaping
- PHP: `echo $_GET['name']` without `htmlspecialchars()`, `{!! $var !!}` in Blade
- Java JSP: `<%= request.getParameter("q") %>` — use `<c:out value="${param.q}"/>`
- Node EJS: `<%- userInput %>` (unescaped) vs `<%= userInput %>` (escaped)
- React: `dangerouslySetInnerHTML={{__html: userInput}}` — DOM XSS vector
- SSTI: `{{7*7}}` in Jinja2/Twig, `${7*7}` in Freemarker/Thymeleaf, `#{7*7}` in Ruby ERB
- Grep: `grep -rnE '(innerHTML|dangerouslySetInnerHTML|\|\s*safe|Markup\(|echo\s+\$_|<%-)' .`

## Path Traversal / LFI
- Python: `open(f"/uploads/{filename}")` — check for `../` sanitization
- PHP: `include($_GET['page'] . ".php")` — null byte or double encoding bypass
- Java: `new File(basePath + request.getParameter("file"))` — use `Path.normalize()` then verify prefix
- Node: `fs.readFile(path.join(uploadDir, req.params.file))` — verify resolved path stays in uploadDir
- Grep: `grep -rnE '(open|include|require|readFile|File\()\s*\(.*(\$_GET|\$_POST|req\.|params|request\.)' .`

## SSRF Sinks
- Python: `requests.get(user_url)`, `urllib.request.urlopen(url)`
- PHP: `file_get_contents($_GET['url'])`, `curl_exec` with user-supplied URL
- Java: `new URL(userUrl).openConnection()`, `HttpClient` with unvalidated URL
- Node: `axios.get(req.body.url)`, `fetch(userInput)`, `http.get(url)`
- Grep: `grep -rnE '(requests\.get|urlopen|file_get_contents|curl_exec|fetch|axios\.(get|post)|http\.get)\s*\(.*\b(url|uri|href|link|callback|webhook|redirect)' .`

## Deserialization
- Python: `pickle.loads(user_data)`, `yaml.load(data)` (without `Loader=SafeLoader`)
- PHP: `unserialize($_COOKIE['data'])` — POP chain to RCE
- Java: `new ObjectInputStream(input).readObject()` — gadget chains (ysoserial)
- Ruby: `Marshal.load(data)`, `YAML.load(user_input)` — use `YAML.safe_load`
- Node: `node-serialize` `unserialize()` — RCE via IIFE `{"rce":"_$$ND_FUNC$$_function(){...}()"}`
- Grep: `grep -rnE '(pickle\.loads|yaml\.load|unserialize|ObjectInputStream|Marshal\.load|\.unserialize)' .`

## Hardcoded Secrets Detection
- `trufflehog filesystem --directory=. --only-verified` — finds verified secrets in source
- `gitleaks detect --source=. --report-format=json --report-path=leaks.json` — scans git history
- Grep patterns: `grep -rnEi '(api[_-]?key|secret|password|token|auth|credential)\s*[:=]\s*["\x27][A-Za-z0-9+/=_-]{16,}' .`
- AWS keys: `grep -rnE 'AKIA[0-9A-Z]{16}' .`
- Private keys: `grep -rnl 'BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY' .`
- JWT secrets: `grep -rnEi 'jwt[_-]?secret\s*[:=]' .`

## SAST Tools
- Semgrep (multi-lang): `semgrep scan --config=auto --config=p/owasp-top-ten --config=p/security-audit .`
- Semgrep custom rule: `semgrep scan --config=p/python.lang.security .` — language-specific packs
- CodeQL: `codeql database create mydb --language=javascript && codeql database analyze mydb javascript-security-and-quality.qls --format=sarif-latest`
- Python: `bandit -r . -f json -o bandit.json` — finds eval, exec, pickle, subprocess, SQL
- Node: `npx eslint --plugin security --rule '{"detect-eval-with-expression":"error"}' .`
- PHP: `phpstan analyse --level=max src/` with security extensions
- Ruby: `brakeman -A -f json -o brakeman.json` — Rails-specific scanner

## Dependency Analysis
- Node: `npm audit --json | jq '.vulnerabilities | to_entries[] | select(.value.severity=="critical")'`
- Python: `pip-audit --format=json --output=audit.json` or `safety check --json`
- Java: `mvn org.owasp:dependency-check-maven:check` — generates HTML report
- Ruby: `bundle audit check --update`
- Go: `govulncheck ./...`
- Universal: `snyk test --all-projects --json > snyk.json`
- Retire.js (JS libs): `retire --path . --outputformat json`

## Audit Workflow
1. Clone repo, run `trufflehog` and `gitleaks` — check full git history for leaked secrets
2. Run `semgrep scan --config=auto` — triage high/critical findings first
3. Run language-specific SAST (bandit/brakeman/eslint-security) for deeper coverage
4. Run `npm audit` / `pip-audit` / `snyk test` for dependency vulnerabilities
5. Manual grep for dangerous sinks: deserialization, eval, exec, system, raw SQL
6. Trace user input from HTTP handlers to sinks — confirm exploitability, not just pattern match
7. Check auth middleware: verify every route is protected, not just a subset
8. Review file upload handlers: extension validation, path construction, storage location
9. Check crypto: hardcoded keys, weak algorithms (MD5/SHA1 for passwords, ECB mode, static IVs)
10. Document findings with file path, line number, code snippet, exploit scenario, remediation
