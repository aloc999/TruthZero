import json
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Optional


class TeamSharing:
    def __init__(self, truthzero_dir: str = "~/.truthzero"):
        self.base_dir = Path(os.path.expanduser(truthzero_dir))

    def export_pack(self, output_path: str, include_skills: bool = True, include_config: bool = True, include_templates: bool = True, include_plugins: bool = True) -> str:
        output = Path(output_path).resolve()
        if not output.suffix:
            output = output.with_suffix(".z0pack")

        with zipfile.ZipFile(str(output), "w", zipfile.ZIP_DEFLATED) as zf:
            manifest = {"version": "0.3.0", "created": time.time(), "contents": []}

            if include_config:
                config_file = self.base_dir / "config.json"
                if config_file.exists():
                    zf.write(str(config_file), "config.json")
                    manifest["contents"].append("config.json")

            if include_skills:
                skills_dir = self.base_dir / "skills"
                if skills_dir.exists():
                    for f in skills_dir.rglob("*"):
                        if f.is_file():
                            arcname = f"skills/{f.relative_to(skills_dir)}"
                            zf.write(str(f), arcname)
                            manifest["contents"].append(arcname)

            if include_plugins:
                plugins_dir = self.base_dir / "plugins"
                if plugins_dir.exists():
                    for f in plugins_dir.rglob("*"):
                        if f.is_file():
                            arcname = f"plugins/{f.relative_to(plugins_dir)}"
                            zf.write(str(f), arcname)
                            manifest["contents"].append(arcname)

            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        return str(output)

    def import_pack(self, pack_path: str, overwrite: bool = False) -> dict:
        pack = Path(pack_path).resolve()
        if not pack.exists():
            return {"error": f"File not found: {pack_path}"}

        imported = {"files": [], "skipped": []}

        with zipfile.ZipFile(str(pack), "r") as zf:
            manifest = {}
            if "manifest.json" in zf.namelist():
                manifest = json.loads(zf.read("manifest.json"))

            for name in zf.namelist():
                if name == "manifest.json":
                    continue

                target = self.base_dir / name
                if target.exists() and not overwrite:
                    imported["skipped"].append(name)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                imported["files"].append(name)

        imported["manifest"] = manifest
        return imported

    def list_exportable(self) -> dict:
        result = {"skills": 0, "plugins": 0, "config": False}
        skills_dir = self.base_dir / "skills"
        if skills_dir.exists():
            result["skills"] = sum(1 for _ in skills_dir.rglob("*") if _.is_file())
        plugins_dir = self.base_dir / "plugins"
        if plugins_dir.exists():
            result["plugins"] = sum(1 for _ in plugins_dir.rglob("*") if _.is_file())
        result["config"] = (self.base_dir / "config.json").exists()
        return result
