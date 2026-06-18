import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Optional


class Plugin:
    def __init__(self, name: str, module: Any, filepath: str = ""):
        self.name = name
        self.module = module
        self.filepath = filepath
        self.description = getattr(module, "DESCRIPTION", name)
        self.version = getattr(module, "VERSION", "0.0.0")
        self.tools = getattr(module, "TOOLS", [])
        self.hooks = getattr(module, "HOOKS", {})

    def get_tools(self) -> list:
        return self.tools

    def get_hooks(self) -> dict:
        return self.hooks


class PluginManager:
    def __init__(self, plugins_dir: str = "~/.zer0code/plugins"):
        self.plugins_dir = Path(os.path.expanduser(plugins_dir))
        self._plugins: dict[str, Plugin] = {}

    def load_all(self) -> dict[str, Plugin]:
        if not self.plugins_dir.exists():
            return {}

        for path in sorted(self.plugins_dir.iterdir()):
            if path.suffix == ".py" and not path.name.startswith("_"):
                self._load_file(path)
            elif path.is_dir() and (path / "__init__.py").exists():
                self._load_package(path)

        return dict(self._plugins)

    def _load_file(self, path: Path) -> Optional[Plugin]:
        name = path.stem
        try:
            spec = importlib.util.spec_from_file_location(f"zer0code_plugin_{name}", str(path))
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            plugin = Plugin(name=name, module=module, filepath=str(path))
            self._plugins[name] = plugin
            return plugin
        except Exception:
            return None

    def _load_package(self, path: Path) -> Optional[Plugin]:
        name = path.name
        try:
            spec = importlib.util.spec_from_file_location(
                f"zer0code_plugin_{name}", str(path / "__init__.py"),
                submodule_search_locations=[str(path)]
            )
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            plugin = Plugin(name=name, module=module, filepath=str(path))
            self._plugins[name] = plugin
            return plugin
        except Exception:
            return None

    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict]:
        return [
            {"name": p.name, "version": p.version, "description": p.description,
             "tools": len(p.tools), "hooks": len(p.hooks), "file": p.filepath}
            for p in self._plugins.values()
        ]

    def get_all_tools(self) -> list:
        tools = []
        for plugin in self._plugins.values():
            tools.extend(plugin.get_tools())
        return tools

    def get_all_hooks(self) -> dict:
        hooks = {}
        for plugin in self._plugins.values():
            for event, callback in plugin.get_hooks().items():
                if event not in hooks:
                    hooks[event] = []
                hooks[event].append(callback)
        return hooks

    @property
    def count(self) -> int:
        return len(self._plugins)

    def create_template(self, name: str) -> str:
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.plugins_dir / f"{name}.py"
        template = f'''DESCRIPTION = "{name} plugin"
VERSION = "0.1.0"

from zer0code.tools.base import BaseTool, ToolResult


class {name.title().replace("-","")}Tool(BaseTool):
    name = "{name}"
    description = "Custom tool from {name} plugin"
    parameters = {{"type": "object", "properties": {{"input": {{"type": "string"}}}}, "required": ["input"]}}

    async def execute(self, input: str = "", **kwargs) -> ToolResult:
        return ToolResult(output=f"Hello from {name}: {{input}}", success=True)


TOOLS = [{name.title().replace("-","")}Tool]
HOOKS = {{}}
'''
        filepath.write_text(template, encoding="utf-8")
        return str(filepath)
