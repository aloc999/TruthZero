# Benchmark Results

> HONEST LABEL: these are **harness-local** numbers from TRUTHZERO's own
> offline suites. They are NOT Cybench / AutoPenBench / CVE-Bench official
> scores. Wiring those harnesses is tracked below.

## Mini-suite (`truthzero bench --suite mini`) — v0.12.0

| Task | Class | Confirm | Mine | JEV keep | JEV drop FP | Pass |
|---|---|---|---|---|---|---|
| bola-idor | BOLA | ✓ | ✓ | ✓ | ✓ | ✓ |
| xss-stored | XSS | ✓ | ✓ | ✓ | ✓ | ✓ |
| sqli-login | SQLi | ✓ | ✓ | ✓ | ✓ | ✓ |
| ssrf-metadata | SSRF | ✓ | ✓ | ✓ | ✓ | ✓ |
| jwt-none | JWT | ✓ | ✓ | ✓ | ✓ | ✓ |

**Score: 5/5 (1.0)** — ingest → miner → JEV pipeline, deterministic, offline.

Method: each task feeds scripted campaign text through
`SwarmScheduler.ingest_text` + `miner` + `JevFilter`, then asserts the
confirmed vuln landed, the refs were mined, JEV kept evidence-backed
findings and dropped the hedge-only note.

## Single (`truthzero bench`) — v0.11.0

Score **0.455** (detection 1/5, precision 0.5, chains 4) on the canned
headless campaign. Baseline only — same-seed comparison across releases.

## Official suites (pending)

| Suite | Status |
|---|---|
| Cybench | planned — needs LLM-backed agent loop + Kali tasks image |
| AutoPenBench | planned — needs full interactive env |
| CVE-Bench | planned — needs CVE-chain container set |
