import hashlib
from collections import deque
from dataclasses import dataclass, field


@dataclass
class LoopDetector:
    window_size: int = 10
    similarity_threshold: float = 0.7
    max_identical_calls: int = 3
    _call_history: deque = field(default_factory=lambda: deque(maxlen=50))
    _hash_counts: dict = field(default_factory=dict)

    def record_call(self, tool_name: str, args: dict, result_hash: str = "") -> None:
        call_sig = f"{tool_name}:{self._normalize_args(args)}"
        call_hash = hashlib.md5(call_sig.encode()).hexdigest()[:12]
        self._call_history.append({"sig": call_sig, "hash": call_hash, "result_hash": result_hash})
        self._hash_counts[call_hash] = self._hash_counts.get(call_hash, 0) + 1

    def is_looping(self) -> bool:
        for count in self._hash_counts.values():
            if count >= self.max_identical_calls:
                return True

        if len(self._call_history) >= self.window_size:
            recent = list(self._call_history)[-self.window_size:]
            hashes = [c["hash"] for c in recent]
            unique_ratio = len(set(hashes)) / len(hashes)
            if unique_ratio < (1.0 - self.similarity_threshold):
                return True

        if len(self._call_history) >= 6:
            recent = list(self._call_history)[-6:]
            result_hashes = [c.get("result_hash", "") for c in recent if c.get("result_hash")]
            if len(result_hashes) >= 4:
                if len(set(result_hashes)) <= 2:
                    return True

        return False

    def get_loop_info(self) -> str:
        if not self.is_looping():
            return ""

        repeated = []
        for sig_hash, count in self._hash_counts.items():
            if count >= self.max_identical_calls:
                for call in self._call_history:
                    if call["hash"] == sig_hash:
                        repeated.append(f"'{call['sig']}' called {count} times")
                        break

        if repeated:
            return f"LOOP DETECTED: {'; '.join(repeated)}. Try a completely different approach."

        return "LOOP DETECTED: Repetitive pattern in recent calls. Change strategy."

    def reset(self):
        self._call_history.clear()
        self._hash_counts.clear()

    def _normalize_args(self, args: dict) -> str:
        try:
            return str(sorted(args.items()))
        except Exception:
            return str(args)
