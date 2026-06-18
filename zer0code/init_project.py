import json
import os
import subprocess
from pathlib import Path
from typing import Optional

from zer0code.file_index import FileIndex


class ProjectInitializer:
    def __init__(self, root: str = "."):
        self.root = Path(root).resolve()
        self.index = FileIndex(str(self.root))

    def generate(self) -> str:
        self.index.scan()
        sections = []

        sections.append(f"# {self.root.name}")
        sections.append("")

        stack = self._detect_stack()
        if stack:
            sections.append("## Tech Stack")
            for tech, detail in stack.items():
                sections.append(f"- **{tech}**: {detail}")
            sections.append("")

        lint_cmd = self._detect_lint()
        test_cmd = self._detect_test()
        build_cmd = self._detect_build()

        if lint_cmd or test_cmd or build_cmd:
            sections.append("## Commands")
            if lint_cmd:
                sections.append(f"- Lint: `{lint_cmd}`")
            if test_cmd:
                sections.append(f"- Test: `{test_cmd}`")
            if build_cmd:
                sections.append(f"- Build: `{build_cmd}`")
            sections.append("")

        structure = self._describe_structure()
        if structure:
            sections.append("## Project Structure")
            for line in structure:
                sections.append(f"- {line}")
            sections.append("")

        conventions = self._detect_conventions()
        if conventions:
            sections.append("## Conventions")
            for conv in conventions:
                sections.append(f"- {conv}")
            sections.append("")

        sections.append("## Notes")
        sections.append("- Add project-specific instructions here")
        sections.append("- ZER0CODE will follow these instructions automatically")
        sections.append("")

        return "\n".join(sections)

    def save(self, filename: str = ".zer0code.md") -> str:
        content = self.generate()
        filepath = self.root / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def _detect_stack(self) -> dict:
        stack = {}
        checks = {
            "package.json": ("Node.js", lambda p: self._read_json_field(p, "name")),
            "pyproject.toml": ("Python", lambda p: "pyproject.toml"),
            "requirements.txt": ("Python", lambda p: "pip"),
            "Cargo.toml": ("Rust", lambda p: "cargo"),
            "go.mod": ("Go", lambda p: "go modules"),
            "pom.xml": ("Java", lambda p: "Maven"),
            "build.gradle": ("Java", lambda p: "Gradle"),
            "Gemfile": ("Ruby", lambda p: "Bundler"),
            "composer.json": ("PHP", lambda p: "Composer"),
            "Dockerfile": ("Docker", lambda p: "containerized"),
            "docker-compose.yml": ("Docker Compose", lambda p: "multi-container"),
            "tsconfig.json": ("TypeScript", lambda p: "tsconfig"),
        }
        for filename, (tech, detail_fn) in checks.items():
            path = self.root / filename
            if path.exists():
                try:
                    stack[tech] = detail_fn(path)
                except Exception:
                    stack[tech] = filename
        return stack

    def _detect_lint(self) -> str:
        checks = [
            ("pyproject.toml", "ruff check ."),
            (".eslintrc.json", "npx eslint ."),
            (".eslintrc.js", "npx eslint ."),
            ("ruff.toml", "ruff check ."),
            (".flake8", "flake8 ."),
            ("Makefile", "make lint"),
        ]
        for filename, cmd in checks:
            if (self.root / filename).exists():
                return cmd
        pkg = self.root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                if "lint" in data.get("scripts", {}):
                    return "npm run lint"
            except Exception:
                pass
        return ""

    def _detect_test(self) -> str:
        checks = [
            ("pyproject.toml", "pytest"),
            ("jest.config.js", "npx jest"),
            ("jest.config.ts", "npx jest"),
            ("vitest.config.ts", "npx vitest"),
            ("Cargo.toml", "cargo test"),
            ("go.mod", "go test ./..."),
        ]
        for filename, cmd in checks:
            if (self.root / filename).exists():
                return cmd
        pkg = self.root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                if "test" in data.get("scripts", {}):
                    return "npm test"
            except Exception:
                pass
        return ""

    def _detect_build(self) -> str:
        checks = [
            ("Makefile", "make build"),
            ("Cargo.toml", "cargo build"),
            ("go.mod", "go build ./..."),
        ]
        for filename, cmd in checks:
            if (self.root / filename).exists():
                return cmd
        pkg = self.root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                if "build" in data.get("scripts", {}):
                    return "npm run build"
            except Exception:
                pass
        return ""

    def _describe_structure(self) -> list[str]:
        lines = []
        ext_counts = self.index.extensions
        top_exts = list(ext_counts.items())[:5]
        if top_exts:
            lines.append(f"{self.index.file_count} files total")
            for ext, count in top_exts:
                lines.append(f"{count} {ext} files")
        return lines

    def _detect_conventions(self) -> list[str]:
        conventions = []
        if (self.root / ".editorconfig").exists():
            conventions.append("EditorConfig for formatting")
        if (self.root / ".prettierrc").exists() or (self.root / ".prettierrc.json").exists():
            conventions.append("Prettier for code formatting")
        if (self.root / ".gitignore").exists():
            conventions.append("Git with .gitignore")
        if (self.root / "LICENSE").exists():
            conventions.append("Licensed project")
        return conventions

    def _read_json_field(self, path: Path, field: str) -> str:
        try:
            data = json.loads(path.read_text())
            return str(data.get(field, path.name))
        except Exception:
            return path.name
