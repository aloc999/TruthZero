import json
import os
from pathlib import Path

BUILTIN_DIR = Path(__file__).parent / "builtin"

SKILL_CATEGORIES = {
    "web": {
        "label": "Web Application",
        "skills": ["web-recon", "api-testing", "xss-hunter", "sqli-master", "ssrf-exploit", "auth-bypass"],
    },
    "infrastructure": {
        "label": "Infrastructure",
        "skills": ["network-pentest", "wireless-attacks", "privesc-linux", "privesc-windows", "ad-attack"],
    },
    "cloud": {
        "label": "Cloud & Containers",
        "skills": ["cloud-pentest", "container-security"],
    },
    "mobile": {
        "label": "Mobile",
        "skills": ["mobile-pentest"],
    },
    "analysis": {
        "label": "Analysis & Forensics",
        "skills": ["reverse-engineering", "malware-analysis", "incident-response", "cryptanalysis"],
    },
    "recon": {
        "label": "Reconnaissance",
        "skills": ["osint", "social-engineering"],
    },
    "methodology": {
        "label": "Methodology",
        "skills": ["bug-bounty", "red-team", "ctf-solving", "source-audit", "report-writing"],
    },
}


class SkillLoader:
    def __init__(self, custom_dir: str = "~/.zer0code/skills"):
        self.custom_dir = Path(os.path.expanduser(custom_dir))
        self._skills: dict = {}
        self._load_builtin()
        self._load_custom()

    def _load_builtin(self):
        if not BUILTIN_DIR.exists():
            return
        for path in sorted(BUILTIN_DIR.iterdir()):
            if path.suffix == ".md":
                skill = self._parse_md(path)
                if skill:
                    self._skills[skill["name"]] = skill

    def _load_custom(self):
        if not self.custom_dir.exists():
            return
        for path in sorted(self.custom_dir.iterdir()):
            if path.suffix == ".md":
                skill = self._parse_md(path)
                if skill:
                    skill["custom"] = True
                    self._skills[skill["name"]] = skill
            elif path.suffix == ".json":
                try:
                    data = json.loads(path.read_text())
                    name = data.get("name", path.stem)
                    self._skills[name] = {
                        "name": name,
                        "description": data.get("description", ""),
                        "system_prompt_addition": data.get("system_prompt_addition", ""),
                        "content": data.get("content", data.get("system_prompt_addition", "")),
                        "category": data.get("category", "custom"),
                        "custom": True,
                    }
                except (json.JSONDecodeError, OSError):
                    continue

    def _parse_md(self, path: Path) -> dict | None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None

        lines = content.strip().splitlines()
        if not lines:
            return None

        name = path.stem
        title = lines[0].lstrip("# ").strip()
        description = ""
        for line in lines[1:]:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped
                break

        category = self._detect_category(name)

        return {
            "name": name,
            "title": title,
            "description": description,
            "system_prompt_addition": content,
            "content": content,
            "category": category,
            "custom": False,
            "file": str(path),
            "lines": len(lines),
        }

    def _detect_category(self, name: str) -> str:
        for cat_key, cat_info in SKILL_CATEGORIES.items():
            if name in cat_info["skills"]:
                return cat_key
        return "custom"

    def get_skill(self, name: str) -> dict | None:
        return self._skills.get(name)

    def get_skill_prompt(self, name: str) -> str:
        skill = self._skills.get(name)
        if skill:
            return skill.get("system_prompt_addition", "")
        return ""

    def list_skills(self) -> list[str]:
        return sorted(self._skills.keys())

    def list_by_category(self) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for skill in self._skills.values():
            cat = skill.get("category", "custom")
            label = SKILL_CATEGORIES.get(cat, {}).get("label", cat.title())
            if label not in result:
                result[label] = []
            result[label].append(skill)
        for skills in result.values():
            skills.sort(key=lambda s: s["name"])
        return result

    def search(self, query: str) -> list[dict]:
        query_lower = query.lower()
        results = []
        for skill in self._skills.values():
            if (
                query_lower in skill["name"].lower()
                or query_lower in skill.get("title", "").lower()
                or query_lower in skill.get("description", "").lower()
            ):
                results.append(skill)
        return results

    @property
    def count(self) -> int:
        return len(self._skills)

    @property
    def builtin_count(self) -> int:
        return sum(1 for s in self._skills.values() if not s.get("custom"))

    @property
    def custom_count(self) -> int:
        return sum(1 for s in self._skills.values() if s.get("custom"))

    def create_custom_skill(self, name: str, title: str, content: str) -> str:
        self.custom_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.custom_dir / f"{name}.md"
        filepath.write_text(f"# {title}\n\n{content}", encoding="utf-8")
        skill = self._parse_md(filepath)
        if skill:
            skill["custom"] = True
            self._skills[name] = skill
        return str(filepath)
