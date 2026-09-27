from truthzero.skills.loader import SkillLoader, SKILL_CATEGORIES

_loader = SkillLoader()
PENTESTING_SKILLS = {name: _loader.get_skill(name) for name in _loader.list_skills()}
