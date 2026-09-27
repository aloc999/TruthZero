import os
from pathlib import Path

IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".tox",
    ".eggs", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".next", ".nuxt", "vendor", "target",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".o", ".a", ".dylib", ".dll",
    ".exe", ".bin", ".dat", ".db", ".sqlite", ".sqlite3",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".zip", ".tar", ".gz",
    ".woff", ".woff2", ".ttf", ".eot",
}


class FileIndex:
    def __init__(self, root: str = "."):
        self.root = Path(root).resolve()
        self._files: list[dict] = []
        self._tree: str = ""

    def scan(self, max_files: int = 5000) -> int:
        self._files = []
        count = 0
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            rel_dir = os.path.relpath(dirpath, self.root)

            for fname in sorted(filenames):
                ext = Path(fname).suffix.lower()
                if ext in IGNORE_EXTENSIONS:
                    continue
                if fname.startswith(".") and fname not in (".env", ".gitignore", ".dockerignore"):
                    continue

                filepath = Path(dirpath) / fname
                rel_path = str(filepath.relative_to(self.root))
                try:
                    size = filepath.stat().st_size
                except OSError:
                    size = 0

                self._files.append({
                    "path": rel_path,
                    "name": fname,
                    "ext": ext,
                    "size": size,
                    "dir": rel_dir if rel_dir != "." else "",
                })

                count += 1
                if count >= max_files:
                    return count

        return count

    def get_tree(self, max_depth: int = 4) -> str:
        if self._tree:
            return self._tree

        lines = [str(self.root.name) + "/"]
        dirs_seen = set()

        for f in self._files:
            parts = Path(f["path"]).parts
            for i, part in enumerate(parts[:-1]):
                if i >= max_depth:
                    break
                prefix_path = "/".join(parts[:i+1])
                if prefix_path not in dirs_seen:
                    dirs_seen.add(prefix_path)
                    indent = "  " * (i + 1)
                    lines.append(f"{indent}{part}/")

            if len(parts) - 1 <= max_depth:
                indent = "  " * len(parts)
                lines.append(f"{indent}{parts[-1]}")

        if len(lines) > 100:
            lines = lines[:100]
            lines.append(f"  ... ({len(self._files)} files total)")

        self._tree = "\n".join(lines)
        return self._tree

    def get_context_prompt(self) -> str:
        if not self._files:
            self.scan()
        tree = self.get_tree()
        return f"PROJECT FILE TREE:\n```\n{tree}\n```\n\nTotal files: {len(self._files)}"

    def search(self, query: str) -> list[str]:
        query_lower = query.lower()
        return [f["path"] for f in self._files if query_lower in f["path"].lower()]

    def get_files_by_ext(self, ext: str) -> list[str]:
        if not ext.startswith("."):
            ext = f".{ext}"
        return [f["path"] for f in self._files if f["ext"] == ext]

    @property
    def file_count(self) -> int:
        return len(self._files)

    @property
    def extensions(self) -> dict[str, int]:
        ext_counts: dict[str, int] = {}
        for f in self._files:
            ext = f["ext"] or "(none)"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        return dict(sorted(ext_counts.items(), key=lambda x: -x[1]))
