import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional


class ResponseCache:
    def __init__(self, cache_dir: str = "~/.zer0code/cache", ttl: int = 3600, max_entries: int = 500):
        self.cache_dir = Path(os.path.expanduser(cache_dir))
        self.ttl = ttl
        self.max_entries = max_entries
        self._memory: dict[str, dict] = {}
        self.hits = 0
        self.misses = 0

    def _hash_key(self, messages: list[dict], model: str) -> str:
        content = json.dumps({"messages": messages, "model": model}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, messages: list[dict], model: str) -> Optional[dict]:
        key = self._hash_key(messages, model)
        entry = self._memory.get(key)
        if entry and (time.time() - entry["timestamp"]) < self.ttl:
            self.hits += 1
            return entry["response"]

        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                if (time.time() - data["timestamp"]) < self.ttl:
                    self._memory[key] = data
                    self.hits += 1
                    return data["response"]
                else:
                    cache_file.unlink(missing_ok=True)
            except Exception:
                pass

        self.misses += 1
        return None

    def set(self, messages: list[dict], model: str, response: dict):
        key = self._hash_key(messages, model)
        entry = {"timestamp": time.time(), "response": response, "model": model}
        self._memory[key] = entry

        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self.cache_dir / f"{key}.json"
            cache_file.write_text(json.dumps(entry))
        except Exception:
            pass

        if len(self._memory) > self.max_entries:
            oldest = sorted(self._memory.items(), key=lambda x: x[1]["timestamp"])
            for k, _ in oldest[:len(oldest) // 4]:
                del self._memory[k]

    def invalidate(self):
        self._memory.clear()
        if self.cache_dir.exists():
            for f in self.cache_dir.glob("*.json"):
                f.unlink(missing_ok=True)

    @property
    def stats(self) -> dict:
        total = self.hits + self.misses
        rate = (self.hits / total * 100) if total > 0 else 0
        return {"hits": self.hits, "misses": self.misses, "hit_rate": f"{rate:.1f}%", "cached": len(self._memory)}

    @property
    def enabled(self) -> bool:
        return self.ttl > 0
