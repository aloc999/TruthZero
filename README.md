<div align="center">

```
 __________ ____   ___   ____ ___  ____  _____ 
|__  / ____|  _ \ / _ \ / ___/ _ \|  _ \| ____|
  / /|  _| | |_) | | | | |  | | | | | | |  _|  
 / /_| |___|  _ <| |_| | |__| |_| | |_| | |___ 
/____|_____|_| \_\\___/ \____\___/|____/|_____|
```

### **Autonomous AI Coding Agent for Expert Penetration Testers**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

</div>

---

ZER0CODE is a terminal-based AI coding agent purpose-built for offensive security professionals. It combines the clean CLI experience of Claude Code, the adaptive learning of Hermes Agent, and a complete penetration testing toolkit — all in one tool.

## What's New in v0.2.0

- MCP (Model Context Protocol) support
- Git tools (status, diff, commit, log, branch)
- Session persistence — save/resume conversations
- Context compaction — automatic context window management
- Permission system — confirms before dangerous actions
- Loop detection — breaks out of repeated failing patterns
- Cost/token tracking with real-time display
- Project context files (.zer0code.md, AGENTS.md)
- Hooks system with auto-lint after code edits
- Subagent system for parallel task spawning
- Diff display when editing files
- TF-IDF semantic memory search
- Episodic memory + adaptive strategy selection
- Meta-cognitive confidence assessment
- DeepSeek LLM provider (V3, R1, V4 Pro)

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
