import json
from zer0code.tools.base import BaseTool, ToolResult


class HttpReplayTool(BaseTool):
    name = "http_replay"
    description = "Send custom HTTP requests with full control over method, headers, body, and cookies. Like Burp Repeater."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], "default": "GET"},
            "headers": {"type": "object", "description": "Custom headers as key-value pairs"},
            "body": {"type": "string", "description": "Request body"},
            "cookies": {"type": "object", "description": "Cookies as key-value pairs"},
            "follow_redirects": {"type": "boolean", "default": False},
            "verify_ssl": {"type": "boolean", "default": True},
            "timeout": {"type": "integer", "default": 30},
        },
        "required": ["url"],
    }

    async def execute(self, url: str = "", method: str = "GET", headers: dict = None, body: str = None, cookies: dict = None, follow_redirects: bool = False, verify_ssl: bool = True, timeout: int = 30, **kwargs) -> ToolResult:
        import httpx
        try:
            cookie_header = "; ".join(f"{k}={v}" for k, v in (cookies or {}).items())
            req_headers = dict(headers or {})
            if cookie_header:
                req_headers["Cookie"] = cookie_header

            async with httpx.AsyncClient(timeout=float(timeout), verify=verify_ssl, follow_redirects=follow_redirects) as client:
                resp = await client.request(method, url, headers=req_headers, content=body)

            output_parts = [
                f"HTTP/{resp.http_version} {resp.status_code} {resp.reason_phrase}",
                "",
            ]
            for k, v in resp.headers.items():
                output_parts.append(f"{k}: {v}")
            output_parts.append("")

            body_text = resp.text
            if len(body_text) > 10000:
                body_text = body_text[:10000] + f"\n\n... (truncated, total {len(resp.text)} chars)"
            output_parts.append(body_text)

            return ToolResult(output="\n".join(output_parts), success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
