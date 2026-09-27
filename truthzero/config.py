from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import os


CONFIG_DIR = Path.home() / ".truthzero"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class SecurityToolsConfig:
    wordlists_path: str = "/usr/share/wordlists"
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 8080
    use_proxy: bool = False


@dataclass
class MCPServerEntry:
    name: str = ""
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class TruthZeroConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    memory_enabled: bool = True
    memory_db_path: str = field(default_factory=lambda: str(CONFIG_DIR / "memory.db"))
    max_context_tokens: int = 128000
    security_tools: SecurityToolsConfig = field(default_factory=SecurityToolsConfig)
    theme: str = "hacker"
    auto_approve_tools: bool = False
    auto_lint: bool = True
    mcp_servers: List[Dict] = field(default_factory=list)
    session_auto_save: bool = True
    token_budget: float = 0.0
    persona: str = "default"
    notifications_enabled: bool = True
    api_server_port: int = 3117
    plugins_enabled: bool = True
    max_turns: int = 25
    # Swarm + verification (Pentest-Swarm-AI parity)
    strict_llm: bool = False       # promote LLM errors to fatal
    prompt_cache: bool = True      # Claude prompt caching for recon+classifier
    jev_enabled: bool = False      # second-opinion FP filter (fails open)
    jev_adaptive: bool = False     # adaptive attack-path scoring (fails open)
    jev_backend: str = "auto"      # auto|builtin|external (TypeSafe Jev, opt-in)
    jev_model: str = "jev-latest"
    jev_base_url: str = ""
    jev_min_severity: str = "high"  # external consulted at/above this
    swarm_rounds: int = 6
    swarm_concurrent: int = 4
    orchestrator_base_url: str = ""

    @property
    def api_key(self) -> Optional[str]:
        if self.provider == "openai":
            return os.environ.get("OPENAI_API_KEY")
        elif self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        elif self.provider == "deepseek":
            return os.environ.get("DEEPSEEK_API_KEY")
        elif self.provider == "glm":
            return os.environ.get("ZHIPU_API_KEY", os.environ.get("ZHIPUAI_API_KEY", ""))
        elif self.provider in ("together", "gemini", "orcarouter", "lmstudio"):
            return os.environ.get("TRUTHZERO_ORCHESTRATOR_API_KEY",
                   os.environ.get("PENTESTSWARM_ORCHESTRATOR_API_KEY",  # legacy
                   os.environ.get("TOGETHER_API_KEY",
                   os.environ.get("GEMINI_API_KEY", ""))))
        return None

    @classmethod
    def load(cls) -> "TruthZeroConfig":
        if not CONFIG_FILE.exists():
            # one-time migration from the old zer0code home
            legacy = Path.home() / ".zer0code" / "config.json"
            if legacy.exists():
                try:
                    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                    CONFIG_FILE.write_text(legacy.read_text())
                except Exception:
                    pass
        if not CONFIG_FILE.exists():
            config = cls()
            config.save()
            return config

        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

        security_tools_data = data.pop("security_tools", {})
        security_tools = SecurityToolsConfig(**security_tools_data)
        mcp_servers = data.pop("mcp_servers", [])

        config = cls(security_tools=security_tools, mcp_servers=mcp_servers, **data)

        project_config = cls._load_project_config()
        if project_config:
            for key, value in project_config.items():
                if key == "security_tools" and isinstance(value, dict):
                    for sk, sv in value.items():
                        setattr(config.security_tools, sk, sv)
                elif key == "mcp_servers" and isinstance(value, list):
                    config.mcp_servers.extend(value)
                elif hasattr(config, key):
                    setattr(config, key, value)

        return config

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get_provider_config(self) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "max_context_tokens": self.max_context_tokens,
        }

        if self.provider == "openai":
            base["api_key"] = os.environ.get("OPENAI_API_KEY", "")
            base["base_url"] = "https://api.openai.com/v1"
        elif self.provider == "anthropic":
            base["api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
            base["base_url"] = "https://api.anthropic.com"
        elif self.provider == "deepseek":
            base["api_key"] = os.environ.get("DEEPSEEK_API_KEY", "")
            base["base_url"] = "https://api.deepseek.com/v1"
        elif self.provider == "ollama":
            base["base_url"] = self.ollama_base_url
            base["api_key"] = "ollama"
        elif self.provider == "together":
            base["api_key"] = os.environ.get("TRUTHZERO_ORCHESTRATOR_API_KEY",
                              os.environ.get("TOGETHER_API_KEY", ""))
            base["base_url"] = self.orchestrator_base_url or "https://api.together.xyz/v1"
        elif self.provider == "gemini":
            base["api_key"] = os.environ.get("TRUTHZERO_ORCHESTRATOR_API_KEY",
                              os.environ.get("GEMINI_API_KEY", os.environ.get("GOOGLE_API_KEY", "")))
            base["base_url"] = self.orchestrator_base_url or "https://generativelanguage.googleapis.com/v1beta/openai"
        elif self.provider == "lmstudio":
            base["api_key"] = "lm-studio"
            base["base_url"] = self.orchestrator_base_url or "http://localhost:1234/v1"
        elif self.provider == "glm":
            base["api_key"] = os.environ.get("ZHIPU_API_KEY",
                              os.environ.get("ZHIPUAI_API_KEY", ""))
            base["base_url"] = self.orchestrator_base_url or "https://open.bigmodel.cn/api/paas/v4"
        elif self.provider == "orcarouter":
            base["api_key"] = os.environ.get("TRUTHZERO_ORCHESTRATOR_API_KEY", "")
            base["base_url"] = self.orchestrator_base_url or "https://api.orcarouter.ai/v1"

        if self.security_tools.use_proxy:
            base["proxy"] = f"http://{self.security_tools.proxy_host}:{self.security_tools.proxy_port}"

        return base

    @staticmethod
    def _load_project_config() -> dict:
        project_files = ["truthzero.json", "truthzero.jsonc", ".truthzero.json"]
        for filename in project_files:
            filepath = Path.cwd() / filename
            if filepath.exists():
                try:
                    content = filepath.read_text()
                    content = "\n".join(line for line in content.splitlines() if not line.strip().startswith("//"))
                    return json.loads(content)
                except Exception:
                    continue
        return {}
