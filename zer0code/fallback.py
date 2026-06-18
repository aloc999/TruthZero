import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FallbackEntry:
    provider: str
    model: str
    priority: int = 0


DEFAULT_CHAIN = [
    FallbackEntry("deepseek", "deepseek-v4-pro", 0),
    FallbackEntry("deepseek", "deepseek-chat", 1),
    FallbackEntry("openai", "gpt-4o", 2),
    FallbackEntry("openai", "gpt-4o-mini", 3),
    FallbackEntry("anthropic", "claude-sonnet-4-20250514", 4),
    FallbackEntry("ollama", "qwen2.5-coder:14b", 5),
]


class ModelFallback:
    def __init__(self, chain: list[FallbackEntry] = None):
        self._chain = sorted(chain or DEFAULT_CHAIN, key=lambda e: e.priority)
        self._current_index = 0
        self._failures: dict[str, int] = {}
        self._on_fallback: Optional[Any] = None

    def set_primary(self, provider: str, model: str):
        primary = FallbackEntry(provider, model, -1)
        self._chain = [primary] + [e for e in self._chain if not (e.provider == provider and e.model == model)]
        self._current_index = 0

    def set_on_fallback(self, callback):
        self._on_fallback = callback

    async def execute(self, provider_factory, call_fn, *args, **kwargs) -> Any:
        last_error = None
        for i, entry in enumerate(self._chain):
            try:
                provider = provider_factory(entry.provider, model=entry.model)
                result = await call_fn(provider, *args, **kwargs)
                if i > 0 and self._on_fallback:
                    try:
                        self._on_fallback(self._chain[0], entry)
                    except Exception:
                        pass
                return result
            except Exception as e:
                key = f"{entry.provider}:{entry.model}"
                self._failures[key] = self._failures.get(key, 0) + 1
                last_error = e
                continue

        raise last_error or RuntimeError("All models in fallback chain failed")

    @property
    def chain_info(self) -> list[dict]:
        return [{"provider": e.provider, "model": e.model, "priority": e.priority, "failures": self._failures.get(f"{e.provider}:{e.model}", 0)} for e in self._chain]

    def reset_failures(self):
        self._failures.clear()
