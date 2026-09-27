from dataclasses import fields
from typing import Any, Optional


VALID_PROVIDERS = {"openai", "anthropic", "deepseek", "ollama",
                   "together", "gemini", "lmstudio", "orcarouter"}
VALID_THEMES = {"hacker", "dark", "minimal"}


class ConfigValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Config validation failed: {'; '.join(errors)}")


class ConfigValidator:
    @staticmethod
    def validate(config_dict: dict) -> list[str]:
        errors = []

        provider = config_dict.get("provider", "")
        if provider and provider not in VALID_PROVIDERS:
            errors.append(f"Invalid provider '{provider}'. Must be one of: {', '.join(VALID_PROVIDERS)}")

        theme = config_dict.get("theme", "")
        if theme and theme not in VALID_THEMES:
            errors.append(f"Invalid theme '{theme}'. Must be one of: {', '.join(VALID_THEMES)}")

        max_tokens = config_dict.get("max_context_tokens", 0)
        if max_tokens and (not isinstance(max_tokens, int) or max_tokens < 1000):
            errors.append(f"max_context_tokens must be an integer >= 1000, got {max_tokens}")

        security = config_dict.get("security_tools", {})
        if isinstance(security, dict):
            port = security.get("proxy_port", 0)
            if port and (not isinstance(port, int) or port < 1 or port > 65535):
                errors.append(f"proxy_port must be 1-65535, got {port}")

        mcp = config_dict.get("mcp_servers", [])
        if not isinstance(mcp, list):
            errors.append("mcp_servers must be a list")
        else:
            for i, server in enumerate(mcp):
                if not isinstance(server, dict):
                    errors.append(f"mcp_servers[{i}] must be a dict")
                elif not server.get("name"):
                    errors.append(f"mcp_servers[{i}] missing 'name'")
                elif not server.get("command"):
                    errors.append(f"mcp_servers[{i}] missing 'command'")

        budget = config_dict.get("token_budget", None)
        if budget is not None and (not isinstance(budget, (int, float)) or budget < 0):
            errors.append(f"token_budget must be a positive number, got {budget}")

        for key in ("strict_llm", "prompt_cache", "jev_enabled", "jev_adaptive",
                    "memory_enabled", "auto_approve_tools", "auto_lint",
                    "session_auto_save", "plugins_enabled", "notifications_enabled"):
            if key in config_dict and not isinstance(config_dict[key], bool):
                errors.append(f"{key} must be a boolean, got {config_dict[key]}")

        for key in ("swarm_rounds", "swarm_concurrent", "max_turns", "api_server_port"):
            if key in config_dict and (not isinstance(config_dict[key], int)
                                       or config_dict[key] < 0):
                errors.append(f"{key} must be a non-negative integer, got {config_dict[key]}")

        jev_backend = config_dict.get("jev_backend", "")
        if jev_backend and jev_backend not in ("auto", "builtin", "external"):
            errors.append(f"jev_backend must be auto|builtin|external, got {jev_backend}")

        jev_min = config_dict.get("jev_min_severity", "")
        if jev_min and jev_min.lower() not in ("critical", "high", "medium", "low", "info"):
            errors.append(f"jev_min_severity must be a severity level, got {jev_min}")

        return errors

    @staticmethod
    def validate_or_raise(config_dict: dict):
        errors = ConfigValidator.validate(config_dict)
        if errors:
            raise ConfigValidationError(errors)

    @staticmethod
    def sanitize(config_dict: dict) -> dict:
        if config_dict.get("provider") not in VALID_PROVIDERS:
            config_dict["provider"] = "openai"
        if config_dict.get("theme") not in VALID_THEMES:
            config_dict["theme"] = "hacker"
        if not isinstance(config_dict.get("max_context_tokens", 0), int):
            config_dict["max_context_tokens"] = 128000
        return config_dict
