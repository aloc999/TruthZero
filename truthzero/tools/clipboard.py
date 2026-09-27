import asyncio
import sys

from truthzero.tools.base import BaseTool, ToolResult


class ClipboardReadTool(BaseTool):
    name = "clipboard_read"
    description = "Read text content from the system clipboard."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs) -> ToolResult:
        try:
            if sys.platform == "darwin":
                proc = await asyncio.create_subprocess_exec("pbpaste", stdout=asyncio.subprocess.PIPE)
                stdout, _ = await proc.communicate()
                return ToolResult(output=stdout.decode("utf-8", errors="replace"), success=True)
            elif sys.platform == "linux":
                for cmd in ["xclip -selection clipboard -o", "xsel --clipboard --output", "wl-paste"]:
                    try:
                        proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        stdout, _ = await proc.communicate()
                        if proc.returncode == 0:
                            return ToolResult(output=stdout.decode("utf-8", errors="replace"), success=True)
                    except Exception:
                        continue
            elif sys.platform == "win32":
                proc = await asyncio.create_subprocess_shell("powershell Get-Clipboard", stdout=asyncio.subprocess.PIPE)
                stdout, _ = await proc.communicate()
                return ToolResult(output=stdout.decode("utf-8", errors="replace"), success=True)
            return ToolResult(output="", success=False, error="No clipboard tool found")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))


class ClipboardWriteTool(BaseTool):
    name = "clipboard_write"
    description = "Write text content to the system clipboard."
    parameters = {"type": "object", "properties": {"content": {"type": "string", "description": "Text to copy to clipboard"}}, "required": ["content"]}

    async def execute(self, content: str = "", **kwargs) -> ToolResult:
        try:
            if sys.platform == "darwin":
                proc = await asyncio.create_subprocess_exec("pbcopy", stdin=asyncio.subprocess.PIPE)
                await proc.communicate(content.encode())
                return ToolResult(output=f"Copied {len(content)} chars to clipboard", success=True)
            elif sys.platform == "linux":
                for cmd in ["xclip -selection clipboard", "xsel --clipboard --input", "wl-copy"]:
                    try:
                        proc = await asyncio.create_subprocess_shell(cmd, stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                        await proc.communicate(content.encode())
                        if proc.returncode == 0:
                            return ToolResult(output=f"Copied {len(content)} chars to clipboard", success=True)
                    except Exception:
                        continue
            elif sys.platform == "win32":
                proc = await asyncio.create_subprocess_shell("clip", stdin=asyncio.subprocess.PIPE)
                await proc.communicate(content.encode())
                return ToolResult(output=f"Copied {len(content)} chars to clipboard", success=True)
            return ToolResult(output="", success=False, error="No clipboard tool found")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
