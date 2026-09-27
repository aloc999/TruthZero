# API Security Testing

REST, GraphQL, and WebSocket API security testing methodology.

## Phase 1: API Discovery
- Swagger/OpenAPI: check `/swagger.json`, `/openapi.json`, `/api-docs`, `/v2/api-docs`, `/swagger-ui.html`
- GraphQL introspection: `{"query":"{__schema{types{name,fields{name,args{name,type{name}}}}}}"}`
- WADL: `/application.wadl`
- Postman collections: check GitHub repos for `.postman_collection.json`
- JS source maps: download `.js.map` files and reconstruct original source

## Phase 2: Authentication Testing
- Test without auth headers (remove Authorization/Cookie)
- JWT analysis: `echo "JWT_TOKEN" | cut -d. -f1,2 | base64 -d 2>/dev/null`
- JWT alg:none: `{"alg":"none","typ":"JWT"}` + unsigned payload
- JWT HS256/RS256 confusion: sign with public key using HS256
- JWT brute: `hashcat -a 0 -m 16500 jwt.txt /usr/share/wordlists/rockyou.txt`
- API key in URL vs header — test if key works across different endpoints
- Bearer token expiry — check if expired tokens still work

## Phase 3: Authorization Testing (BOLA/IDOR)
- Swap user IDs: GET /api/users/123 → GET /api/users/124
- Swap UUIDs: capture UUID from user A, use in user B's session
- Parameter pollution: `/api/users?id=123&id=456`
- HTTP method override: `X-HTTP-Method-Override: DELETE` on GET request
- GraphQL node query: `{node(id:"base64_of_other_user_id"){...on User{email,ssn}}}`
- Test sequential IDs, UUID predictability, and encoded IDs

## Phase 4: Input Validation
- Mass assignment: POST `{"username":"test","role":"admin","is_admin":true}`
- SQL injection in API params: `{"search":"' OR 1=1--"}`
- NoSQL injection: `{"username":{"$gt":""},"password":{"$gt":""}}`
- SSRF via URL params: `{"webhook_url":"http://169.254.169.254/latest/meta-data/"}`
- XXE in XML APIs: Include DOCTYPE with external entity
- Prototype pollution: `{"__proto__":{"isAdmin":true}}`

## Phase 5: Rate Limiting & Business Logic
- Test rate limits: send 100 requests rapidly to auth endpoints
- Bypass rate limits: rotate X-Forwarded-For, X-Real-IP headers
- Race conditions: parallel requests to transfer/payment endpoints
- Negative values: `{"amount":-100,"quantity":-1}`
- Large values: integer overflow on quantity/price fields
- Parameter tampering: modify price/discount in request body

## GraphQL Specific
```graphql
# Introspection
{__schema{queryType{name}mutationType{name}types{name,fields{name}}}}

# Batching attack (bypass rate limits)
[{"query":"mutation{login(u:\"admin\",p:\"pass1\")}"}, {"query":"mutation{login(u:\"admin\",p:\"pass2\")}"}]

# Deep query DoS
{user{friends{friends{friends{friends{name}}}}}}

# Field suggestion exploitation
{user{DOESNOTEXIST}}  # Error may reveal valid field names
```

## Tips
- Document every endpoint, method, parameter, and response code
- Test CORS: `Origin: https://evil.com` — check `Access-Control-Allow-Origin` response
- Always test horizontal AND vertical authorization
- Check if DELETE/PUT methods work when only GET/POST documented
- Look for debug endpoints: `/api/debug`, `/api/test`, `/api/health`
- Check for verbose error messages leaking stack traces
