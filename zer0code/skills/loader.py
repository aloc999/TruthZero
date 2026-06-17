import json
import os
from pathlib import Path

from zer0code.skills.pentesting import PENTESTING_SKILLS


class SkillLoader:
    def __init__(self, skills_dir: str = "~/.zer0code/skills"):
        self.skills_dir = Path(os.path.expanduser(skills_dir))
        self._skills: dict = {}
        self._skills.update(self.load_builtin_skills())
        self._skills.update(self.load_custom_skills())

    def load_builtin_skills(self) -> dict:
        return dict(PENTESTING_SKILLS)

    def load_custom_skills(self) -> dict:
        custom = {}
        if not self.skills_dir.exists():
            return custom

        for path in self.skills_dir.iterdir():
            if path.suffix == ".json":
                try:
                    data = json.loads(path.read_text())
                    name = data.get("name", path.stem)
                    custom[name] = {
                        "name": name,
                        "description": data.get("description", ""),
                        "system_prompt_addition": data.get("system_prompt_addition", ""),
                    }
                except (json.JSONDecodeError, OSError):
                    continue
            elif path.suffix == ".md":
                try:
                    content = path.read_text()
                    name = path.stem
                    lines = content.strip().splitlines()
                    description = lines[0].lstrip("# ").strip() if lines else name
                    prompt_body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
                    custom[name] = {
                        "name": name,
                        "description": description,
                        "system_prompt_addition": prompt_body,
                    }
                except OSError:
                    continue

        return custom

    def get_skill(self, name: str) -> dict | None:
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        return sorted(self._skills.keys())

    def get_skill_prompt(self, name: str) -> str:
        skill = self._skills.get(name)
        if skill:
            return skill.get("system_prompt_addition", "")
        return ""
