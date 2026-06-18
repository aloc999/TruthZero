import difflib
import os
import subprocess
from datetime import datetime
from typing import Optional


class RollbackManager:
    def __init__(self):
        self._snapshots: dict[str, str] = {}
        self._timestamps: dict[str, str] = {}

    def snapshot(self, filepath: str):
        abspath = os.path.abspath(filepath)
        content = self._read_file(abspath)
        if content is not None:
            self._snapshots[abspath] = content
            self._timestamps[abspath] = datetime.now().isoformat()

    def rollback(self, filepath: str) -> bool:
        abspath = os.path.abspath(filepath)
        if abspath not in self._snapshots:
            return False
        try:
            self._write_file(abspath, self._snapshots[abspath])
            return True
        except Exception:
            return False

    def rollback_all(self) -> list[str]:
        restored = []
        for abspath, content in self._snapshots.items():
            try:
                self._write_file(abspath, content)
                restored.append(abspath)
            except Exception:
                pass
        return restored

    def list_changes(self) -> list[dict]:
        changes = []
        for filepath in self._snapshots:
            changes.append({
                "filepath": filepath,
                "has_snapshot": True,
                "modified_at": self._timestamps.get(filepath, ""),
            })
        return changes

    def git_stash(self) -> str:
        try:
            result = subprocess.run(
                ["git", "stash"],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            return str(e)

    def git_undo_last_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "reset", "--soft", "HEAD~1"],
                capture_output=True, text=True, timeout=30
            )
            return result.stdout.strip() or result.stderr.strip() or "Reset successful"
        except Exception as e:
            return str(e)

    def diff(self, filepath: str) -> str:
        abspath = os.path.abspath(filepath)
        if abspath not in self._snapshots:
            return ""
        original = self._snapshots[abspath].splitlines(keepends=True)
        current_content = self._read_file(abspath)
        if current_content is None:
            return ""
        current = current_content.splitlines(keepends=True)
        return "".join(difflib.unified_diff(
            original, current,
            fromfile=f"a/{filepath}",
            tofile=f"b/{filepath}",
        ))

    def clear(self):
        self._snapshots.clear()
        self._timestamps.clear()

    def _read_file(self, path: str) -> Optional[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    def _write_file(self, path: str, content: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
