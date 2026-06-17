from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any
import json
import os


CONFIG_DIR = Path.home() / ".zer0code"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class SecurityToolsConfig:
    wordlists_path: str = "/usr/share/wordlists"
    proxy_host: str = "127.0.0.1"
    proxy_port: int = 8080
    use_proxy: bool = False


@dataclass
class ZeroCodeConfig:
    provider: str = "openai"
    model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    memory_enabled: bool = True
    memory_db_path: str = field(default_factory=lambda: str(CONFIG_DIR / "memory.db"))
    max_context_tokens: int = 128000
    security_tools: SecurityToolsConfig = field(default_factory=SecurityToolsConfig)
    theme: str = "hacker"

    @property
    def api_key(self) -> Optional[str]:
        if self.provider == "openai":
            return os.environ.get("OPENAI_API_KEY")
        elif self.provider == "anthropic":
            return os.environ.get("ANTHROPIC_API_KEY")
        elif self.provider == "deepseek":
            return os.environ.get("DEEPSEEK_API_KEY")
        return None

    @classmethod
    def load(cls) -> "ZeroCodeConfig":
        if not CONFIG_FILE.exists():
            config = cls()
            config.save()
            return config

        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)

        security_tools_data = data.pop("security_tools", {})
        security_tools = SecurityToolsConfig(**security_tools_data)

        config = cls(security_tools=security_tools, **data)
        return config

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get_provider_config(self) -> Dict[str, Any]:
        base = {
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

        if self.security_tools.use_proxy:
            base["proxy"] = f"http://{self.security_tools.proxy_host}:{self.security_tools.proxy_port}"

        return base
