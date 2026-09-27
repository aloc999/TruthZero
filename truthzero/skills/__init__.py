from truthzero.skills.loader import SKILL_CATEGORIES, SkillLoader

_loader = SkillLoader()
PENTESTING_SKILLS = {name: _loader.get_skill(name) for name in _loader.list_skills()}

__all__ = [
    "SKILL_CATEGORIES",
    "SkillLoader",
]
