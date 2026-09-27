"""Burp REST-API bridge — proxy history, Repeater, scope sync.

Talks to the community Burp REST API extension (vmware/burp-rest-api,
default http://127.0.0.1:1337). All calls fail open with a clear
"not reachable" message — never crash the agent. Scope is enforced at
the agent executor layer; Burp-side scope is synced via `scope_add`.
"""
from __future__ import annotations

import json

import httpx

from zer0code.tools.base import BaseTool, ToolResult

DEFAULT_BURP_API = "http://127.0.0.1:1337"


class BurpBridgeTool(BaseTool):
    name = "burp_bridge"
    description = (
        "Bridge to Burp Suite via REST API: proxy history, Repeater send, "
        "scope sync. Actions: history|repeater|scope_add|scope_get|status."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["status", "history", "repeater", "scope_add", "scope_get"],
                       "default": "status"},
            "base_url": {"type": "string", "default": DEFAULT_BURP_API},
            "api_key": {"type": "string", "description": "Burp REST API key (if set)"},
            "target": {"type": "string", "description": "URL (history filter / repeater / scope_add)"},
            "method": {"type": "string", "default": "GET"},
            "headers": {"type": "string", "description": "JSON object of headers for repeater"},
            "body": {"type": "string", "description": "Body for repeater"},
            "limit": {"type": "integer", "default": 20},
        },
        "required": ["action"],
    }

    async def execute(self, action: str = "status", base_url: str = DEFAULT_BURP_API,
                      api_key: str = "", target: str = "", method: str = "GET",
                      headers: str = "", body: str = "", limit: int = 20,
                      **kwargs) -> ToolResult:
        base = (base_url or DEFAULT_BURP_API).rstrip("/")
        hdrs = {"Content-Type": "application/json"}
        if api_key:
            hdrs["Authorization"] = api_key
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if action == "status":
                    return await self._status(client, base, hdrs)
                if action == "history":
                    return await self._history(client, base, hdrs, target, limit)
                if action == "repeater":
                    return await self._repeater(client, base, hdrs, target, method,
                                                headers, body)
                if action == "scope_add":
                    return await self._scope(client, base, hdrs, target, add=True)
                if action == "scope_get":
                    return await self._scope(client, base, hdrs, target, add=False)
                return ToolResult(output="", success=False, error=f"Unknown action: {action}")
        except httpx.ConnectError:
            return ToolResult(output="", success=False,
                              error=f"Burp REST API not reachable at {base}. "
                                    "Start Burp + REST API extension (default :1337).")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"burp_bridge error: {e}")

    async def _status(self, client, base, hdrs) -> ToolResult:
        try:
            r = await client.get(f"{base}/burp/versions", headers=hdrs)
            if r.status_code == 200:
                return ToolResult(output=f"Burp REST API up: {r.text[:500]}", success=True)
            return ToolResult(output="", success=False,
                              error=f"Burp API status {r.status_code}: {r.text[:300]}")
        except httpx.ConnectError:
            raise
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

    async def _history(self, client, base, hdrs, target, limit) -> ToolResult:
        try:
            r = await client.get(f"{base}/burp/proxy/history", headers=hdrs)
        except httpx.ConnectError:
            raise
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
        if r.status_code != 200:
            return ToolResult(output="", success=False,
                              error=f"history failed ({r.status_code}): {r.text[:300]}")
        try:
            items = r.json()
        except Exception:
            return ToolResult(output=r.text[:4000], success=True)
        if isinstance(items, dict):
            items = items.get("messages", items.get("history", []))
        lines = []
        for it in (items or [])[:limit * 2]:
            url = it.get("url", it.get("request", {}).get("url", ""))
            if target and target.lower() not in str(url).lower():
                continue
            lines.append(f"  {it.get('method', ''):<6} {it.get('statuscode', it.get('status', ''))}  {url}")
            if len(lines) >= limit:
                break
        return ToolResult(output="\n".join(lines) or "No history entries.", success=True)

    async def _repeater(self, client, base, hdrs, target, method, headers, body) -> ToolResult:
        if not target:
            return ToolResult(output="", success=False, error="repeater needs target URL")
        try:
            h = json.loads(headers) if headers else {}
        except Exception:
            h = {}
        payload = {"request": {"method": method, "url": target,
                               "headers": h, "body": body or ""}}
        r = await client.put(f"{base}/burp/repeater", headers=hdrs, json=payload)
        if r.status_code not in (200, 201):
            return ToolResult(output="", success=False,
                              error=f"repeater failed ({r.status_code}): {r.text[:500]}")
        return ToolResult(output=r.text[:6000], success=True)

    async def _scope(self, client, base, hdrs, target, add: bool) -> ToolResult:
        if add:
            if not target:
                return ToolResult(output="", success=False, error="scope_add needs target")
            r = await client.put(f"{base}/burp/target/scope",
                                 headers=hdrs, json={"url": target})
            ok = r.status_code in (200, 201)
            return ToolResult(output=r.text[:1000] if ok else "",
                              success=ok,
                              error="" if ok else f"scope_add failed: {r.text[:300]}")
        r = await client.get(f"{base}/burp/target/scope", headers=hdrs)
        return ToolResult(output=r.text[:4000], success=r.status_code == 200)
