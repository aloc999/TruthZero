"""Playbook + chain loaders (YAML, no hard dependency — tiny parser)."""
from __future__ import annotations

from pathlib import Path


def _tiny_yaml_parse(text: str) -> dict:
    """Minimal YAML subset parser: top-level keys, lists, nested one level."""
    root: dict = {}
    stack: list[tuple[int, dict | list, str | None]] = [(0, root, None)]
    lines = [ln.rstrip() for ln in text.splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    for ln in lines:
        indent = len(ln) - len(ln.lstrip(" "))
        content = ln.strip()
        # find parent
        while stack and indent < stack[-1][0]:
            stack.pop()
        parent, key = stack[-1][1], stack[-1][2]
        if content.startswith("- "):
            item = content[2:].strip().strip('"')
            if isinstance(parent, dict) and key:
                parent.setdefault(key, [])
                parent[key].append(item)
            elif isinstance(parent, list):
                parent.append(item)
        elif ":" in content:
            k, _, v = content.partition(":")
            k, v = k.strip(), v.strip().strip('"')
            if isinstance(parent, dict):
                if v == "":
                    # nested block: peek — assume dict unless next is list
                    parent[k] = {}
                    stack.append((indent + 2, parent[k], None))
                    # remember last key for list items
                    stack[-2] = (stack[-2][0], stack[-2][1], k)
                else:
                    if v.lower() in ("true", "false"):
                        parent[k] = v.lower() == "true"
                    else:
                        try:
                            parent[k] = int(v)
                        except ValueError:
                            parent[k] = v
            elif isinstance(parent, list):
                parent.append({k: v} if v else {k: {}})
    return root


def _parse_simple_yaml(text: str) -> dict:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except Exception:
        return _tiny_yaml_parse(text)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_yaml_file(path: str) -> dict:
    """Parse any YAML file (PyYAML if present, else tiny subset parser)."""
    return _parse_simple_yaml(Path(path).read_text())


def list_playbooks() -> list[str]:
    d = _repo_root() / "playbooks"
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_playbook(name: str) -> dict:
    p = _repo_root() / "playbooks" / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"Playbook not found: {name}")
    return _parse_simple_yaml(p.read_text())


def list_chains() -> list[str]:
    d = _repo_root() / "chains"
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_chain(name: str) -> dict:
    p = _repo_root() / "chains" / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"Chain not found: {name}")
    return _parse_simple_yaml(p.read_text())
