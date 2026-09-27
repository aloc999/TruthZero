<div align="center">

```
  ░▒▓█████████████████████████████████████████████████▓▒░

    █████ █████ ████   ███   ████  ███  ████  █████
       █  █     █   █ █   █ █     █   █ █   █ █    
      █   ████  ████  █ ▀ █ █     █   █ █   █ ████ 
     █    █     █  █  █   █ █     █   █ █   █ █    
    █████ █████ █   █  ███   ████  ███  ████  █████

  ░▒▓█████████████████████████████████████████████████▓▒░

              ⚡ No tools Are Perfect ⚡
```

### **AI Coding Agent for Penetration Testing**

[![npm](https://img.shields.io/badge/npm-zer0code-red.svg)](https://www.npmjs.com/package/zer0code)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

</div>

---

ZER0CODE is a terminal-based AI coding agent purpose-built for offensive security professionals. It combines the clean CLI experience of Freedom, adaptive learning, and a complete penetration testing toolkit — all in one tool.

## What's New in v0.9.0 — Swarm Edition 🐝

Inspired by [Pentest-Swarm-AI](https://github.com/Armur-Ai/Pentest-Swarm-AI): ZER0CODE is now a **real swarm**, not a pipeline.

- **Stigmergic blackboard + pheromone decay** — agents coordinate via shared findings; `PORT_OPEN` stays hot for hours, `SESSION` for minutes; stale paths decay and die (`zer0code/swarm/`)
- **4 concurrent specialists** — recon / classify / exploit / report, each with its own trigger predicate; attack chains *emerge* instead of being scripted
- **Adaptive attack-path scoring** (`--jev-adaptive`) — candidate paths scored against live state, best pursued first, winners reinforced
- **JEV false-positive filter** (`--jev`) — second-opinion pass, fails open
- **CVSS v3.1 scoring** — FIRST-spec vectors on every finding
- **5 playbooks** — `playbooks/{bug-bounty,external-asm,ci-cd,internal-network,ctf-solver}.yaml`
- **Exploit-chain library** — `chains/*.yaml` (SSRF→RCE, auth-bypass→RCE, BOLA/IDOR, SSTI→RCE, takeover)
- **New providers** — Together AI (GLM/Qwen/DeepSeek first-class), Gemini, LM Studio, OrcaRouter
- **New CLI** — `scan --swarm`, `playbook`, `demo`, `install-tools`, `doctor`, `mcp serve`, `serve` (dashboard stub :7777)
- **SARIF export** — CI-ready `zer0code-results.sarif`
- **Scope defence in depth** — tool layer + executor layer, fail closed; **cleanup registry** (SIGINT/crash/budget)

```bash
zer0code scan target.com --scope target.com --swarm          # scriptable swarm
zer0code lab up crapi                                       # bundled vuln lab (docker)
zer0code scan 127.0.0.1 --scope 127.0.0.1 --swarm            # attack the lab
zer0code playbook run bug-bounty --target target.com
zer0code demo                                                # offline campaign demo
zer0code bench                                               # offline benchmark score
zer0code gate --sarif zer0code-results.sarif                 # CI quality gate
zer0code asm diff old.json new.json                          # ASM delta
zer0code mcp serve                                           # MCP stdio server
```

## What's New in v0.11.0 — Wave 3 🧠

- **Self-correcting attacks** — 401/403/415/429/5xx feed back into header/backoff mutations; heals instead of dead-ending
- **Response miner** — every tool output mined for URLs, params, emails, UUIDs, secrets → one leak becomes emergent BOLA probes
- **On-demand specialists** — `auth-holder`, `param-fuzzer`, `chain-builder` spawn when board state warrants, die when done
- **Real labs** — `zer0code lab up/down crapi|juice|vampi|dvga` (docker, teardown on exit); `scan --lab` spins up for real
- **Memory-poisoning guard** — injection patterns, quotas, control-char checks before Hermes learns
- **Bench harness** — `zer0code bench` scores detection/precision/chaining; training recipe in `docs/training-recipe.md`
- **Green suite** — 43 passed, 0 failed (async-runner fallback in `conftest.py`, `BaseTool.schema()` for all tools)

## What's New in v0.10.0 — Wave 2 🌊

- **Burp bridge** (`burp_bridge` tool) — proxy history, Repeater send, scope sync via Burp REST API (:1337), fails clean when Burp is down
- **Real MCP server** — `zer0code mcp serve` speaks JSON-RPC stdio (9 tools: blackboard, playbooks, chains, CVSS, burp) for Claude Desktop / Cursor
- **sqlmap / Metasploit / ZAP adapters** — safe defaults only (sqlmap level2/risk1, msf scanner-allowlist, ZAP baseline); destructive flags refused
- **ASM diffing + CI gate** — snapshot, diff vs previous, `gate` exits 2 on high/critical; GitHub Action uploads SARIF
- **Postgres board** (beta) — transactional writes + pheromone decay in SQL, fails open to memory board
- **VS Code extension** (beta) + **GitHub Action** in `deploy/`

See [ROADMAP.md](ROADMAP.md) for Wave 2/3 and [SECURITY.md](SECURITY.md) for scope safety.

### ZER0CODE vs Pentest-Swarm-AI

| | ZER0CODE v0.9 | Pentest-Swarm-AI |
|---|---|---|
| Open / self-host | ✅ MIT, Python | ✅ AGPL, Go |
| Architecture | Stigmergic blackboard (ported) | Stigmergic blackboard (original) |
| Executes vs suggests | Executes | Executes |
| Memory | Hermes TF-IDF + episodic + strategies | pgvector + pheromones |
| Tools | 30+ (bash/git/recon/nuclei/exploit/crypto) + PD toolchain wrapper | 8 ProjectDiscovery + nmap |
| Attack-path scoring | Adaptive (graded pheromone) | JEV adaptive |
| FP filter | JEV-style, fails open | JEV, fails open |
| Playbooks | 5 YAML | 5 YAML |
| Exploit chains | YAML library, CVE-tied | Named CVE-tied chains |
| Providers | OpenAI/Anthropic/DeepSeek/Together/Gemini/Ollama/LMStudio/OrcaRouter | Claude/Together/Gemini/OrcaRouter/Ollama/LMStudio |
| Labs / demo | lab flag + demo (stub spin-up) | bundled labs + demo GIF |
| Dashboard | alpha stub | alpha |
| MCP | client + serve stub | server beta + Burp planned |

## What's New in v0.3.0

**24 new features added:**

- Image/vision input — analyze screenshots and images with vision-capable models
- Streaming tool output — watch long-running tools (nmap, ffuf) in real-time
- Extended thinking — support for o1/o3/R1 reasoning tokens
- Session export — generate markdown/HTML penetration test reports from sessions
- Rate limit retry — automatic exponential backoff on API errors
- Context window indicator — see how full your context is (%)
- Token budget — set a spending cap per session
- Agent personas — switch between red-team, bug-hunter, code-reviewer, dfir, ctf-player modes
- Proxy integration — route tool requests through Burp Suite / Caido
- Undo/rollback — revert any file changes the agent made
- Autocomplete — tab-completion for all slash commands
- Prompt templates — 15 reusable templates for common pentesting tasks
- Dockerfile — run ZER0CODE in a container with pentesting tools
- CI/CD pipeline — GitHub Actions for testing and publishing
- Config validation — catches invalid settings on load
- 19 tests — pytest test suite for tools, memory, and config
- Full-screen TUI — split-pane terminal view (experimental)
- LSP integration — get code diagnostics from language servers
- Conversation branching — fork conversations to try different approaches
- Python plugin system — extend with custom tools via ~/.zer0code/plugins/
- Desktop notifications — alerts when long tasks complete
- API server mode — run as HTTP API at localhost:3117
- Encrypted credential storage — secure local key management
- Fuzzy search — autocomplete with history suggestions

---

## Features

### Agentic AI Core
- **Autonomous tool execution** — agent plans, executes tools, observes results, and iterates
- **Multi-provider LLM support** — OpenAI, Anthropic, DeepSeek, Ollama (local models)
- **Streaming responses** with real-time rendering
- **Parallel tool execution** — runs independent tools concurrently
- **Loop detection** — detects and breaks repetitive patterns automatically
- **Context compaction** — summarizes old messages when context fills up (`/compact`)
- **Permission system** — confirms before high-risk actions (bash, port scan, nuclei, etc.)
- **Cost tracking** — real-time token and dollar tracking per model

### Learn from Mistakes (Hermes-style Memory)
- **TF-IDF semantic search** — finds relevant memories using term frequency, not just keywords
- **Mistake tracking** — records errors, extracts lessons, avoids repeating failures
- **Success patterns** — remembers what worked for future reference
- **Episodic memory** — full episode replay with tool call sequences
- **Adaptive strategy selection** — picks different approaches based on what worked before
- **Memory decay** — old irrelevant memories fade, recent ones stay prominent
- **Auto-reflection triggers** — reflects after 3 consecutive tool failures or 5 total session failures
- **Meta-cognitive confidence assessment** — self-evaluates whether it's making progress or stuck
- **Cross-project learning** — applies lessons from one project to another
- **Loop detection** — detects when stuck in a cycle and forces strategy change

### MCP (Model Context Protocol)
- Connect to any MCP server via stdio transport
- Register external tools dynamically
- Configure servers in `~/.zer0code/config.json`

### Session Persistence
- Auto-save conversations to SQLite
- Resume any previous session with `--resume <id>`
- List, load, title, and delete sessions
- Full message history including tool calls

### Project Context
- Auto-detects project root (git, config files)
- Loads `.zer0code.md` or `AGENTS.md` for project-specific instructions
- Detects tech stack (Python, Node, Rust, Go, Java, Docker, etc.)
- Injects project context into system prompt

### Penetration Testing Toolkit (25 Built-in Tools)

| Category | Tools |
|----------|-------|
| **Core** | Bash, Read File, Write File, Edit File, Glob, Grep, Web Fetch |
| **Git** | Status, Diff, Commit, Log, Branch |
| **Recon** | Subdomain Enumeration, Port Scanning, DNS Lookup, WHOIS |
| **Scanning** | Nuclei Integration, Directory Fuzzing, Tech Detection |
| **Exploitation** | Exploit Search (NVD/ExploitDB), Payload Generator, Reverse Shell Generator |
| **Crypto** | Hash Identification, Hash Cracking, Encoder/Decoder |

### Terminal UI (Claude Code-inspired)
- Clean, minimal interface with rich markdown rendering
- 3 themes: `hacker` (green-on-black), `dark` (modern), `minimal`
- Tool execution panels with spinners and syntax highlighting
- Diff display when editing files
- Status bar with model, tokens, cost, and memory count
- Permission confirmation dialogs for dangerous actions

### Hooks & Auto-Lint
- Pre/post tool execution hooks
- Auto-lint after file writes (ruff, eslint, gofmt, cargo clippy)
- Extensible hook system

### 15 Built-in Pentesting Skills
Web Recon, API Testing, XSS Hunter, SQLi Master, SSRF Exploit, Auth Bypass, Linux PrivEsc, Windows PrivEsc, AD Attack, Cloud Pentest, Mobile Pentest, Network Pentest, Reverse Engineering, Malware Analysis, OSINT

---

## Installation

### npm (Recommended)

```bash
npm install -g zer0code
```

That's it. The installer automatically sets up Python, creates a virtual environment, and installs all dependencies.

### pip (Alternative)

```bash
git clone https://github.com/aloc999/zer0code.git
cd zer0code
pip install -e .
```

### Requirements
- Python 3.10+
- An LLM API key (OpenAI, Anthropic, DeepSeek) or Ollama running locally

### Optional (for full pentesting capability)
```bash
# Recon
apt install subfinder amass nmap whois dnsutils

# Scanning
apt install nuclei ffuf gobuster

# Exploitation
apt install exploitdb hashcat john
```

---

## Quick Start

```bash
# Set API key
export OPENAI_API_KEY="sk-..."       # OpenAI
export ANTHROPIC_API_KEY="sk-ant-..."  # Anthropic
export DEEPSEEK_API_KEY="sk-..."       # DeepSeek

# Interactive mode
zer0code

# With specific provider/model
zer0code -p deepseek -m deepseek-v4-pro

# Single prompt
zer0code run "scan target.com for open ports"

# Resume a session
zer0code --resume abc123

# List past sessions
zer0code sessions
```

### Interactive Commands
```
/help       Show all commands
/tools      List available tools (with risk levels)
/clear      Clear conversation history
/memory     View learned memories and stats
/config     Show current configuration
/model      Switch model (/model deepseek-v4-pro)
/provider   Switch provider (/provider deepseek)
/theme      Switch theme (/theme dark)
/skill      Load a pentesting skill (/skill xss-hunter)
/session    Manage sessions (list/load/title)
/compact    Compact conversation context
/cost       Show token usage and cost
/status     Show status bar
/persona    Switch agent persona (red-team, bug-hunter, dfir, etc.)
/template   Run a prompt template (/template scan-web target.com)
/proxy      Configure Burp/Caido proxy (/proxy on|off|test)
/branch     Fork conversations (/branch create|switch|list|merge)
/export     Export session to report (/export report.html)
/undo       Rollback file changes (/undo all|list|<file>)
/plugin     Manage plugins (/plugin list|create|load)
/serve      Start API server (/serve start|stop)
/budget     Set token budget (/budget 5.00)
/creds      Manage credentials (/creds set|get|list|delete)
/lsp        Code diagnostics (/lsp <filepath>)
/exit       Exit ZER0CODE
```

---

## Configuration

Config file: `~/.zer0code/config.json`

```json
{
  "provider": "deepseek",
  "model": "deepseek-v4-pro",
  "theme": "hacker",
  "memory_enabled": true,
  "auto_approve_tools": false,
  "auto_lint": true,
  "session_auto_save": true,
  "max_context_tokens": 128000,
  "security_tools": {
    "wordlists_path": "/usr/share/wordlists",
    "proxy_host": "127.0.0.1",
    "proxy_port": 8080,
    "use_proxy": false
  },
  "mcp_servers": [
    {
      "name": "filesystem",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "enabled": true
    }
  ]
}
```

### Provider Options

| Provider | Models | Notes |
|----------|--------|-------|
| `openai` | gpt-4o, gpt-4o-mini, o3-mini | Requires OPENAI_API_KEY |
| `anthropic` | claude-sonnet-4-20250514, claude-opus-4-20250514 | Requires ANTHROPIC_API_KEY |
| `deepseek` | deepseek-chat, deepseek-reasoner, deepseek-v4-pro | Requires DEEPSEEK_API_KEY |
| `ollama` | qwen2.5-coder, llama3.1, deepseek-coder-v2 | Local, no API key needed |

---

## Project Context

Create a `.zer0code.md` file in your project root:

```markdown
# Project Instructions

This is a Django REST API with PostgreSQL.
Always use pytest for testing.
Run `make lint` after code changes.
Security focus: check for SQLi in ORM queries.
```

ZER0CODE auto-loads this and follows the instructions.

Supported context files (checked in order):
- `.zer0code.md`
- `.zer0code`
- `AGENTS.md`
- `CLAUDE.md`
- `.github/copilot-instructions.md`

---

## Architecture

```
zer0code/
├── agent.py              # Core agentic loop (parallel tools, loop detection, compaction)
├── cli.py                # CLI interface (click + prompt_toolkit + TerminalUI)
├── config.py             # Configuration with MCP server support
├── cost.py               # Token/cost tracking per provider
├── context.py            # Project context + context compaction
├── hooks.py              # Hook system + auto-lint
├── permissions.py        # Permission/risk management
├── session.py            # Session persistence (SQLite)
├── subagent.py           # Parallel subagent spawning
├── export.py             # Session export to markdown/HTML reports
├── personas.py           # Agent persona definitions and switching
├── plugins.py            # Python plugin loader (~/.zer0code/plugins/)
├── server.py             # HTTP API server (localhost:3117)
├── credentials.py        # Encrypted credential storage
├── templates.py          # Prompt template engine
├── rollback.py           # File change undo/rollback tracking
├── notifications.py      # Desktop notification integration
├── lsp.py                # LSP client for code diagnostics
├── branching.py          # Conversation branching/forking
├── providers/            # LLM provider integrations
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   ├── deepseek_provider.py
│   └── ollama_provider.py
├── tools/                # Tool system (25 tools)
│   ├── bash.py
│   ├── file_ops.py
│   ├── search.py
│   ├── git.py            # Git integration
│   └── security/         # Pentesting tools
│       ├── recon.py
│       ├── scanner.py
│       ├── exploit.py
│       └── crypto.py
├── memory/               # Hermes-style learning system
│   ├── store.py          # TF-IDF semantic search + episodic + strategies
│   ├── reflection.py     # Auto-reflection + meta-cognition + strategy
│   └── loop_detector.py  # Loop/stuck pattern detection
├── mcp/                  # Model Context Protocol client
│   └── client.py
├── ui/                   # Terminal UI
│   ├── terminal.py
│   ├── themes.py
│   ├── components.py
│   └── diff.py           # Diff renderer
└── skills/               # Pentesting skills
    ├── pentesting.py
    └── loader.py
```

---

## Memory System

ZER0CODE learns from every session with 6 memory types:

| Type | Purpose |
|------|---------|
| **Mistakes** | Records failures and extracts lessons |
| **Successes** | Remembers approaches that worked |
| **Tool Patterns** | Learns optimal tool usage |
| **Knowledge** | Accumulates security knowledge |
| **Episodes** | Full tool-call sequence replay |
| **Strategies** | Adaptive approach selection with success rates |

Features:
- **TF-IDF semantic search** — finds relevant memories by meaning, not just keywords
- **Exponential decay** — old memories fade, recent ones stay relevant
- **Auto-reflection** — triggers after consecutive failures
- **Loop detection** — breaks out of repeated patterns
- **Confidence assessment** — monitors if agent is making progress
- **Cross-project** — learns transfer across projects

---

## Permission System

Tools are categorized by risk level:

| Risk | Tools | Behavior |
|------|-------|----------|
| **Low** | read, glob, grep, dns_lookup, whois | Auto-approved |
| **Medium** | write, edit, commit, payload_gen, hash_crack | Contextual |
| **High** | bash, port_scan, nuclei, dir_fuzz, reverse_shell | Requires confirmation |

Dangerous command patterns (rm -rf, DROP TABLE, etc.) always require confirmation.

Set `"auto_approve_tools": true` in config to skip confirmations.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-tool`)
3. Commit your changes (`git commit -m 'Add new tool'`)
4. Push to the branch (`git push origin feature/new-tool`)
5. Open a Pull Request

---

## Disclaimer

ZER0CODE is designed for **authorized security testing only**. Always obtain proper authorization before testing any system. The authors are not responsible for misuse of this tool.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built for the offensive security community.**

*"In the world of zeros and ones, we are the zero that makes everything possible."*

</div>
