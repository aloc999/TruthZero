# ZER0CODE Roadmap

Honesty labels: *stable* = shipped + tested, *beta* = works, rough edges,
*alpha* = experimental, *planned* = future.

## Wave 1 — Swarm parity (this release)
| Feature | Status | Notes |
|---|---|---|
| Sequential pipeline (RECON→ANALYSIS→EXPLOIT→REPORT) | **stable** | `zer0code/pipeline.py` |
| Stigmergic swarm scheduler | **beta** | `zer0code/swarm/` — blackboard + pheromone + 4 specialists |
| Pheromone decay per finding type | **beta** | `FINDING_HALF_LIVES`, PORT_OPEN hours / SESSION minutes |
| ProjectDiscovery toolchain wrapper | **beta** | subfinder·httpx·nuclei·naabu·katana·dnsx·gau·nmap, scope-checked |
| CVSS v3.1 scoring | **beta** | FIRST spec, `zer0code/scoring/cvss.py` |
| JEV FP filter | **beta** | `--jev`, fails open |
| Adaptive attack-path scoring | **beta** | `--jev-adaptive`, graded pheromone |
| Scope enforcement (tool + executor) | **stable** | defence in depth, fail closed |
| Cleanup registry | **stable** | SIGINT/crash/budget, reverse-order |
| Playbooks (5) | **beta** | `playbooks/*.yaml` |
| Exploit chains library | **beta** | `chains/*.yaml` |
| Providers: together/gemini/lmstudio/orcarouter | **beta** | OpenAI-compatible + Claude/Ollama |
| SARIF export | **beta** | `ReportGenerator.to_sarif/write_sarif`, CI-ready |
| Dashboard | **alpha** | `web/index.html` stub, wiring in progress |
| MCP serve | **beta** | `zer0code mcp serve` (stdio bridge Wave 2) |

## Wave 2
- Burp MCP bridge (full replay/scope sync)
- sqlmap / Metasploit / ZAP adapters
- Playbook polish (ASM diffing, CI gate)
- Postgres + pgvector blackboard backend (memory-board now)
- VS Code extension, GitHub Action + SARIF in Marketplace

## Wave 3
- Fine-tuned offensive model recipe (Pentest-R1 style)
- Cybench / AutoPenBench / CVE-Bench numbers
- Agent-memory poisoning hardening
- Self-correcting attacks (closed-loop replanning on 401/403/415)
- On-demand specialist sub-agents (auth holder, param fuzzer, chain builder)
- Runtime reaction to discoveries (mine every response → emergent BOLA)
