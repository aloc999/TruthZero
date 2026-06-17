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

ZER0CODE is a terminal-based AI coding agent purpose-built for offensive security professionals. It combines the clean CLI experience of modern AI coding tools with a complete penetration testing toolkit, adaptive memory that learns from past mistakes, and multi-provider LLM support.

## Features

### Agentic AI Core
- **Autonomous tool execution** — agent plans, executes tools, observes results, and iterates
- **Multi-provider LLM support** — OpenAI, Anthropic, DeepSeek, Ollama (local models)
- **Streaming responses** with real-time rendering
- **Conversation context** with intelligent management

### Learn from Mistakes (Hermes-style Memory)
- **Mistake tracking** — records errors, extracts lessons, avoids repeating failures
- **Success patterns** — remembers what worked for future reference
- **Tool patterns** — learns optimal tool usage over time
- **Knowledge base** — accumulates security knowledge across sessions
- **Reflection engine** — periodically analyzes behavior and extracts insights

### Penetration Testing Toolkit (13 Built-in Security Tools)

| Category | Tools |
|----------|-------|
| **Recon** | Subdomain Enumeration, Port Scanning, DNS Lookup, WHOIS |
| **Scanning** | Nuclei Integration, Directory Fuzzing, Tech Detection |
| **Exploitation** | Exploit Search (NVD/ExploitDB), Payload Generator, Reverse Shell Generator |
| **Crypto** | Hash Identification, Hash Cracking, Encoder/Decoder |

### Core Development Tools
- **Bash** — execute any shell command
- **File Operations** — read, write, edit, glob, grep
- **Web Fetch** — retrieve and parse web content

### Terminal UI
- Clean, Claude Code-inspired interface
- 3 themes: `hacker` (green-on-black), `dark` (modern), `minimal`
- Rich markdown rendering with syntax highlighting
- Tool execution panels with spinners
- Status bar with token tracking

### 15 Built-in Pentesting Skills
Web Recon • API Testing • XSS Hunter • SQLi Master • SSRF Exploit • Auth Bypass • Linux PrivEsc • Windows PrivEsc • AD Attack • Cloud Pentest • Mobile Pentest • Network Pentest • Reverse Engineering • Malware Analysis • OSINT

---

## Installation

```bash
# Clone the repository
git clone https://github.com/aloc999/zer0code.git
cd zer0code

# Install
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

### Requirements
- Python 3.10+
- An LLM API key (OpenAI, Anthropic) or Ollama running locally

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

### Set your API key
```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# DeepSeek
export DEEPSEEK_API_KEY="sk-..."

# Or use Ollama (no key needed)
# Just have Ollama running: ollama serve
```

### Launch ZER0CODE
```bash
# Interactive mode
zer0code

# Short alias
z0

# Single prompt
zer0code run "scan target.com for open ports"

# Show config
zer0code config

# Show learned memories
zer0code memory
```

### Interactive Commands
```
/help       — Show all commands
/tools      — List available tools
/clear      — Clear conversation
/memory     — View learned memories
/config     — Show configuration
/model      — Switch model
/provider   — Switch provider
/skill      — Load a pentesting skill
/exit       — Exit ZER0CODE
```

---

## Configuration

Config file: `~/.zer0code/config.json`

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "theme": "hacker",
  "memory_enabled": true,
  "max_context_tokens": 128000,
  "security": {
    "proxy": null,
    "wordlists_path": "/usr/share/wordlists"
  }
}
```

### Provider Options

| Provider | Models | Notes |
|----------|--------|-------|
| `openai` | gpt-4o, gpt-4o-mini, o1, o3 | Requires OPENAI_API_KEY |
| `anthropic` | claude-sonnet-4-20250514, claude-opus-4-20250514 | Requires ANTHROPIC_API_KEY |
| `deepseek` | deepseek-chat, deepseek-reasoner, deepseek-v4-pro | Requires DEEPSEEK_API_KEY |
| `ollama` | qwen2.5-coder, llama3.1, deepseek-coder-v2 | Local, no API key needed |

---

## Architecture

```
zer0code/
├── agent.py              # Core agentic loop
├── cli.py                # CLI interface (click + prompt_toolkit)
├── config.py             # Configuration management
├── providers/            # LLM provider integrations
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   └── ollama_provider.py
├── tools/                # Tool system
│   ├── bash.py           # Shell execution
│   ├── file_ops.py       # File operations
│   ├── search.py         # Web fetching
│   └── security/         # Pentesting tools
│       ├── recon.py      # Subdomain enum, port scan, DNS, WHOIS
│       ├── scanner.py    # Nuclei, dir fuzz, tech detect
│       ├── exploit.py    # Exploit search, payloads, reverse shells
│       └── crypto.py     # Hash ID, cracking, encoding
├── memory/               # Learning system
│   ├── store.py          # SQLite memory store
│   └── reflection.py     # Mistake analysis engine
├── ui/                   # Terminal UI
│   ├── terminal.py       # Main UI controller
│   ├── themes.py         # Color themes
│   └── components.py     # UI components
└── skills/               # Pentesting skills
    ├── pentesting.py     # Built-in skill definitions
    └── loader.py         # Skill loading system
```

---

## Usage Examples

### Web Application Recon
```
> Enumerate subdomains for target.com and scan for open ports
```

### Vulnerability Assessment
```
> Run nuclei scan on https://target.com with high severity templates
```

### Exploit Development
```
> Search for CVEs related to Apache 2.4.49 and generate exploit payloads
```

### Code Review
```
> Read the source code in ./src and identify SQL injection vulnerabilities
```

### Reverse Shell
```
> Generate a Python reverse shell for 10.10.14.5:4444
```

### Hash Cracking
```
> Identify this hash: 5f4dcc3b5aa765d61d8327deb882cf99 and try to crack it
```

---

## Memory System

ZER0CODE learns from every session:

- **Mistakes** → "Last time nmap failed because the host was behind a WAF. Next time, use `--script http-waf-detect` first."
- **Successes** → "ffuf with `-fc 403,404` and medium wordlist found `/api/v2/admin` on similar targets."
- **Patterns** → "For Spring Boot apps, always check `/actuator/env` and `/actuator/heapdump`."

Memories persist in `~/.zer0code/memory.db` and are automatically injected into context when relevant.

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
