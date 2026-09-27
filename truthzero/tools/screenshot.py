import asyncio
import time
from pathlib import Path

from truthzero.tools.base import BaseTool, ToolResult


class ScreenshotTool(BaseTool):
    name = "screenshot"
    description = "Capture a screenshot of a web page. Uses gowitness, cutycapt, or wkhtmltoimage."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to screenshot"},
            "output": {"type": "string", "description": "Output file path"},
            "width": {"type": "integer", "default": 1280},
            "height": {"type": "integer", "default": 1024},
        },
        "required": ["url"],
    }

    async def execute(self, url: str = "", output: str = "", width: int = 1280, height: int = 1024, **kwargs) -> ToolResult:
        if not output:
            safe_name = url.replace("://", "_").replace("/", "_").replace(".", "_")[:50]
            output = f"screenshot_{safe_name}_{int(time.time())}.png"

        output_path = Path(output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        methods = [
            self._try_gowitness,
            self._try_cutycapt,
            self._try_wkhtmltoimage,
            self._try_playwright,
        ]

        for method in methods:
            result = await method(url, str(output_path), width, height)
            if result:
                return result

        return ToolResult(
            output="",
            success=False,
            error="No screenshot tool found. Install one of: gowitness, cutycapt, wkhtmltoimage, or playwright (pip install playwright && playwright install chromium)"
        )

    async def _run(self, cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode == 0, (stdout or stderr or b"").decode("utf-8", errors="replace")
        except FileNotFoundError:
            return False, "not found"
        except asyncio.TimeoutError:
            return False, "timeout"
        except Exception as e:
            return False, str(e)

    async def _try_gowitness(self, url: str, output: str, w: int, h: int) -> ToolResult | None:
        ok, msg = await self._run(["gowitness", "single", url, "--screenshot-path", str(Path(output).parent), "--resolution-x", str(w), "--resolution-y", str(h)])
        if ok:
            return ToolResult(output=f"Screenshot saved: {output} (gowitness)", success=True)
        if "not found" in msg:
            return None
        return None

    async def _try_cutycapt(self, url: str, output: str, w: int, h: int) -> ToolResult | None:
        ok, msg = await self._run(["cutycapt", f"--url={url}", f"--out={output}", f"--min-width={w}", f"--min-height={h}"])
        if ok:
            return ToolResult(output=f"Screenshot saved: {output} (cutycapt)", success=True)
        if "not found" in msg:
            return None
        return None

    async def _try_wkhtmltoimage(self, url: str, output: str, w: int, h: int) -> ToolResult | None:
        ok, msg = await self._run(["wkhtmltoimage", "--width", str(w), "--height", str(h), "--quality", "85", url, output])
        if ok:
            return ToolResult(output=f"Screenshot saved: {output} (wkhtmltoimage)", success=True)
        if "not found" in msg:
            return None
        return None

    async def _try_playwright(self, url: str, output: str, w: int, h: int) -> ToolResult | None:
        try:
            script = f"""
import asyncio
from playwright.async_api import async_playwright
async def shot():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={{'width': {w}, 'height': {h}}})
        await page.goto('{url}', wait_until='networkidle', timeout=20000)
        await page.screenshot(path='{output}', full_page=True)
        await browser.close()
asyncio.run(shot())
"""
            proc = await asyncio.create_subprocess_exec(
                "python3", "-c", script,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                return ToolResult(output=f"Screenshot saved: {output} (playwright)", success=True)
        except Exception:
            pass
        return None
