# TRUTHZERO Roadmap

Honesty labels: *stable* = shipped + tested, *beta* = works, rough edges,
*alpha* = experimental, *planned* = future.

## Wave 1 — Swarm parity (this release)
| Feature | Status | Notes |
|---|---|---|
| Sequential pipeline (RECON→ANALYSIS→EXPLOIT→REPORT) | **stable** | `truthzero/pipeline.py` |
| Stigmergic swarm scheduler | **beta** | `truthzero/swarm/` — blackboard + pheromone + 4 specialists |
| Pheromone decay per finding type | **beta** | `FINDING_HALF_LIVES`, PORT_OPEN hours / SESSION minutes |
| ProjectDiscovery toolchain wrapper | **beta** | subfinder·httpx·nuclei·naabu·katana·dnsx·gau·nmap, scope-checked |
| CVSS v3.1 scoring | **beta** | FIRST spec, `truthzero/scoring/cvss.py` |
| JEV FP filter | **beta** | `--jev`, fails open |
| Adaptive attack-path scoring | **beta** | `--jev-adaptive`, graded pheromone |
| Scope enforcement (tool + executor) | **stable** | defence in depth, fail closed |
| Cleanup registry | **stable** | SIGINT/crash/budget, reverse-order |
| Playbooks (5) | **beta** | `playbooks/*.yaml` |
| Exploit chains library | **beta** | `chains/*.yaml` |
| Providers: together/gemini/lmstudio/orcarouter | **beta** | OpenAI-compatible + Claude/Ollama |
| SARIF export | **beta** | `ReportGenerator.to_sarif/write_sarif`, CI-ready |
| Dashboard | **alpha** | `web/index.html` stub, wiring in progress |
| MCP serve | **beta** | `truthzero mcp serve` (stdio bridge Wave 2) |

## Wave 2 (shipped in v0.10.0)
| Feature | Status | Notes |
|---|---|---|
| Burp MCP bridge | **beta** | `burp_bridge` tool (history/repeater/scope via REST :1337) |
| MCP stdio server | **beta** | `truthzero mcp serve` — 9 tools, Claude/Cursor-ready |
| sqlmap adapter | **beta** | safe defaults, destructive flags blocked |
| Metasploit adapter | **beta** | scanner/gather/check allowlist, no payloads |
| ZAP adapter | **beta** | baseline + api-scan via zap-cli/Docker |
| ASM diffing | **beta** | `truthzero asm diff`, new assets → blackboard |
| CI gate | **stable** | `truthzero gate --sarif`, exit 2 on fail_on |
| Postgres board backend | **beta** | `PostgresBoard`, decay in SQL, fails open |
| VS Code extension | **beta** | `deploy/vscode/` |
| GitHub Action + SARIF | **beta** | `deploy/github-action/` |

## Wave 3

## Wave 3 (shipped in v0.11.0)
| Feature | Status | Notes |
|---|---|---|
| Self-correcting attacks | **beta** | `swarm/selfheal.py` — status-driven mutations + backoff |
| Runtime reaction to discoveries | **beta** | `swarm/miner.py` — URLs/params/emails/UUIDs/secrets → board |
| On-demand specialists | **beta** | `swarm/specialists.py` — auth-holder/param-fuzzer/chain-builder |
| Vulnerable labs (docker) | **beta** | `truthzero/lab.py` — crapi/juice/vampi/dvga, cleanup-registered |
| Memory-poisoning guard | **beta** | `memory/guard.py` — injection/quotas/controls |
| Bench harness | **alpha** | `truthzero bench` local score; Cybench/AutoPenBench/CVE-Bench pending |
| Training recipe | **alpha** | `docs/training-recipe.md` (SFT+RL recipe, no weights) |
| Green test suite | **stable** | 43 passed, 0 failed |

## v0.15 — Campaign Watch (shipped)
| Feature | Status | Notes |
|---|---|---|
| ESC works (picker dismiss + panel close + input refocus) | **stable** | pilot-tested |
| GLM provider (Zhipu direct, OpenAI-compat) | **beta** | `ZHIPU_API_KEY`, coding-plan base-url override |
| Scheduler on_event hook (per-round progress) | **stable** | swarm + sequential modes |
| TUI live campaign panel (NOW ▸ / pills / severity / findings) | **beta** | mirrors live-campaign TUI functionally |

## v0.14 — Real Jev (shipped)
| Feature | Status | Notes |
|---|---|---|
| External TypeSafe Jev backend (System One API, opt-in) | **beta** | `scoring/jev_external.py`, `TYPESAFE_API_KEY` |
| AND-gate: drop only if builtin + external agree | **stable** | conflict/abstain → keep for human review |
| Severity gate (external only at high+) | **stable** | `jev_min_severity`, paid calls go where FPs cost most |
| Doctor Jev status line | **stable** | builtin-only vs external-ready |
| Wired flags: --no-swarm sequential, --jev sweep, --strict exit codes | **stable** | `headless.py` modes, `strict_llm` honored |

## v0.13 — Live Grid (shipped)
| Feature | Status | Notes |
|---|---|---|
| Neon SVG hero banner (browser-verified) | **stable** | `banner/hero.svg`, README hero |
| Live dashboard + HTTP API | **beta** | `truthzero/dashboard.py` — GET /, /api/findings, /api/sarif, POST /api/scan (403 OOS) |
| Shared headless runner (CLI + API) | **stable** | `truthzero/headless.py`, boards persist to `~/.truthzero/boards/` |

## v0.12 — Benchmarks + pgvector + Marketplace (shipped)
| Feature | Status | Notes |
|---|---|---|
| Mini benchmark suite (5 tasks, ingest→mine→JEV) | **stable** | `benchmarks/tasks/`, `bench --suite mini` → 5/5 |
| RESULTS.md with honest harness-local numbers | **stable** | `benchmarks/RESULTS.md` |
| pgvector embeddings (hashing default, pluggable model) | **beta** | `PostgresBoard.ensure_vector/similar` |
| VS Code Marketplace packaging | **beta** | `deploy/vscode/` + vsce docs |
| GitHub Action Marketplace flow | **beta** | `deploy/github-action/README.md` + `v0` moving tag |
| Release pipeline (test→PyPI→major tag→asset check) | **stable** | `.github/workflows/release.yml` |
| Cyberpunk README rewrite | **stable** | chrome banner, full deck docs |

## Next
- Cybench / AutoPenBench / CVE-Bench official envs (harness ready)
- Real embedding model option (Ollama/Together) behind `embed_fn`
- `vsce publish` + Marketplace listing live (packaging ready)
- pgvector HNSW index tuning at scale
