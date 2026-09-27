import asyncio
import json
from typing import Optional
from truthzero.tools.base import BaseTool, ToolResult


class AuthSessionTool(BaseTool):
    name = "auth_session"
    description = "Manage authenticated sessions — login, store cookies/tokens, make authenticated requests. Maintains state across calls."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["login", "request", "set_cookie", "set_header", "show", "clear"], "description": "Action to perform"},
            "url": {"type": "string", "description": "URL for login or request"},
            "method": {"type": "string", "default": "POST"},
            "body": {"type": "string", "description": "Request body (JSON or form data)"},
            "content_type": {"type": "string", "default": "application/json"},
            "cookie_name": {"type": "string", "description": "Cookie name to set manually"},
            "cookie_value": {"type": "string", "description": "Cookie value"},
            "header_name": {"type": "string", "description": "Header name to persist"},
            "header_value": {"type": "string", "description": "Header value to persist"},
            "follow_redirects": {"type": "boolean", "default": True},
        },
        "required": ["action"],
    }

    _cookies: dict = {}
    _headers: dict = {}
    _history: list = []

    async def execute(self, action: str = "", url: str = "", method: str = "POST", body: str = "", content_type: str = "application/json", cookie_name: str = "", cookie_value: str = "", header_name: str = "", header_value: str = "", follow_redirects: bool = True, **kwargs) -> ToolResult:
        import httpx

        if action == "login":
            if not url:
                return ToolResult(output="", success=False, error="URL required for login")
            try:
                headers = {"Content-Type": content_type, **self._headers}
                cookie_str = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
                if cookie_str:
                    headers["Cookie"] = cookie_str

                async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=follow_redirects) as client:
                    resp = await client.request(method, url, headers=headers, content=body if body else None)

                    for name, val in resp.cookies.items():
                        self._cookies[name] = val

                    for h in resp.headers.get_list("set-cookie"):
                        parts = h.split(";")[0].split("=", 1)
                        if len(parts) == 2:
                            self._cookies[parts[0].strip()] = parts[1].strip()

                    auth_header = resp.headers.get("authorization", "")
                    if auth_header:
                        self._headers["Authorization"] = auth_header

                    self._history.append({"action": "login", "url": url, "status": resp.status_code})

                    output = f"Login: {resp.status_code} {resp.reason_phrase}\n"
                    output += f"Cookies captured: {list(self._cookies.keys())}\n"
                    output += f"Response headers:\n"
                    for k, v in resp.headers.items():
                        if k.lower() in ("set-cookie", "location", "authorization", "x-csrf-token"):
                            output += f"  {k}: {v}\n"
                    body_preview = resp.text[:500]
                    output += f"\nBody: {body_preview}"
                    return ToolResult(output=output, success=True)
            except Exception as e:
                return ToolResult(output="", success=False, error=str(e))

        elif action == "request":
            if not url:
                return ToolResult(output="", success=False, error="URL required")
            try:
                headers = {"Content-Type": content_type, **self._headers}
                cookie_str = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
                if cookie_str:
                    headers["Cookie"] = cookie_str

                async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=follow_redirects) as client:
                    resp = await client.request(method, url, headers=headers, content=body if body else None)

                    for name, val in resp.cookies.items():
                        self._cookies[name] = val

                    self._history.append({"action": "request", "url": url, "method": method, "status": resp.status_code})

                    output = f"HTTP/{resp.http_version} {resp.status_code} {resp.reason_phrase}\n\n"
                    for k, v in resp.headers.items():
                        output += f"{k}: {v}\n"
                    output += f"\n{resp.text[:3000]}"
                    return ToolResult(output=output, success=True)
            except Exception as e:
                return ToolResult(output="", success=False, error=str(e))

        elif action == "set_cookie":
            if cookie_name and cookie_value:
                self._cookies[cookie_name] = cookie_value
                return ToolResult(output=f"Cookie set: {cookie_name}={cookie_value[:20]}...", success=True)
            return ToolResult(output="", success=False, error="cookie_name and cookie_value required")

        elif action == "set_header":
            if header_name and header_value:
                self._headers[header_name] = header_value
                return ToolResult(output=f"Header set: {header_name}: {header_value[:30]}...", success=True)
            return ToolResult(output="", success=False, error="header_name and header_value required")

        elif action == "show":
            output = f"Cookies ({len(self._cookies)}):\n"
            for k, v in self._cookies.items():
                output += f"  {k}={v[:30]}{'...' if len(v) > 30 else ''}\n"
            output += f"\nPersistent headers ({len(self._headers)}):\n"
            for k, v in self._headers.items():
                output += f"  {k}: {v[:50]}\n"
            output += f"\nHistory ({len(self._history)} requests)"
            return ToolResult(output=output, success=True)

        elif action == "clear":
            self._cookies.clear()
            self._headers.clear()
            self._history.clear()
            return ToolResult(output="Session cleared.", success=True)

        return ToolResult(output="", success=False, error=f"Unknown action: {action}")
