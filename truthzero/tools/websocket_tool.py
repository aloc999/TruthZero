import asyncio
import json
from truthzero.tools.base import BaseTool, ToolResult


class WebSocketTool(BaseTool):
    name = "websocket_test"
    description = "Connect to a WebSocket endpoint, send messages, and receive responses."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "WebSocket URL (ws:// or wss://)"},
            "messages": {"type": "array", "items": {"type": "string"}, "description": "Messages to send"},
            "headers": {"type": "object", "description": "Custom headers"},
            "timeout": {"type": "integer", "default": 10},
            "max_responses": {"type": "integer", "default": 5},
        },
        "required": ["url"],
    }

    async def execute(self, url: str = "", messages: list = None, headers: dict = None, timeout: int = 10, max_responses: int = 5, **kwargs) -> ToolResult:
        try:
            import websockets
        except ImportError:
            return ToolResult(
                output=self._fallback_test(url, messages or [], timeout),
                success=True,
            )

        try:
            extra_headers = headers or {}
            responses = []

            async with websockets.connect(url, extra_headers=extra_headers, open_timeout=timeout) as ws:
                responses.append(f"Connected to {url}")

                for msg in (messages or []):
                    await ws.send(msg)
                    responses.append(f">>> {msg}")

                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        responses.append(f"<<< {resp}")
                    except asyncio.TimeoutError:
                        responses.append("<<< (timeout)")

                recv_count = 0
                while recv_count < max_responses:
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=2)
                        responses.append(f"<<< {resp}")
                        recv_count += 1
                    except (asyncio.TimeoutError, Exception):
                        break

            return ToolResult(output="\n".join(responses), success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

    def _fallback_test(self, url: str, messages: list, timeout: int) -> str:
        return f"WebSocket connection to {url}\nNote: Install 'websockets' package for full support.\nMessages to send: {len(messages)}"
