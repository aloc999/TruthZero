from typing import Optional


class UpdateChecker:
    NPM_URL = "https://registry.npmjs.org/truthzero/latest"
    PYPI_URL = "https://pypi.org/pypi/truthzero/json"

    @staticmethod
    async def check_npm(current_version: str) -> Optional[dict]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(UpdateChecker.NPM_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    latest = data.get("version", current_version)
                    if latest != current_version:
                        return {"current": current_version, "latest": latest, "source": "npm", "update_cmd": "npm update -g truthzero"}
        except Exception:
            pass
        return None

    @staticmethod
    async def check_pypi(current_version: str) -> Optional[dict]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(UpdateChecker.PYPI_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    latest = data.get("info", {}).get("version", current_version)
                    if latest != current_version:
                        return {"current": current_version, "latest": latest, "source": "pypi", "update_cmd": "pip install --upgrade truthzero"}
        except Exception:
            pass
        return None

    @staticmethod
    async def check(current_version: str) -> Optional[dict]:
        result = await UpdateChecker.check_npm(current_version)
        if result:
            return result
        return await UpdateChecker.check_pypi(current_version)

    @staticmethod
    def format_update_message(info: dict) -> str:
        return f"Update available: {info['current']} -> {info['latest']}\nRun: {info['update_cmd']}"
