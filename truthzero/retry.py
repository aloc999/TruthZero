import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class RetryConfig:
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status: set = field(default_factory=lambda: {429, 500, 502, 503, 504})


class RetryHandler:
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self._attempt_count: int = 0
        self._total_retries: int = 0
        self._on_retry: Optional[Callable] = None

    def set_on_retry(self, callback: Callable):
        self._on_retry = callback

    def _calculate_delay(self, attempt: int) -> float:
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        delay = min(delay, self.config.max_delay)
        if self.config.jitter:
            delay = delay * (0.5 + random.random())
        return delay

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            self._attempt_count = attempt
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                last_error = e
                error_str = str(e)

                is_rate_limit = "429" in error_str or "rate limit" in error_str.lower()
                is_server_error = any(str(code) in error_str for code in [500, 502, 503, 504])

                if not (is_rate_limit or is_server_error):
                    raise

                if attempt >= self.config.max_retries:
                    raise

                delay = self._calculate_delay(attempt)
                self._total_retries += 1

                if self._on_retry:
                    try:
                        self._on_retry(attempt + 1, delay, str(e))
                    except Exception:
                        pass

                await asyncio.sleep(delay)

        raise last_error

    @property
    def total_retries(self) -> int:
        return self._total_retries

    def reset_stats(self):
        self._total_retries = 0
        self._attempt_count = 0
