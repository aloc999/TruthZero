import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class MCPTool:
    name: str
    description: str
    parameters: dict
    server_name: str


class MCPClient:
    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._tools: dict[str, MCPTool] = {}
        self._request_id: int = 0

    def add_server(self, config: MCPServerConfig):
        self._servers[config.name] = config

    async def connect_all(self) -> dict[str, list[MCPTool]]:
        results = {}
        for name, config in self._servers.items():
            if not config.enabled:
                continue
            try:
                tools = await self._connect_server(name, config)
                results[name] = tools
            except Exception as e:
                results[name] = []
        return results

    async def _connect_server(self, name: str, config: MCPServerConfig) -> list[MCPTool]:
        env = {**os.environ, **config.env}
        proc = await asyncio.create_subprocess_exec(
            config.command,
            *config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._processes[name] = proc

        await self._send_jsonrpc(proc, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "zer0code", "version": "0.1.0"},
        })
        response = await self._read_jsonrpc(proc)

        await self._send_jsonrpc_notification(proc, "notifications/initialized", {})

        await self._send_jsonrpc(proc, "tools/list", {})
        tools_response = await self._read_jsonrpc(proc)

        tools = []
        for tool_data in tools_response.get("result", {}).get("tools", []):
            tool = MCPTool(
                name=f"{name}__{tool_data['name']}",
                description=tool_data.get("description", ""),
                parameters=tool_data.get("inputSchema", {"type": "object", "properties": {}}),
                server_name=name,
            )
            self._tools[tool.name] = tool
            tools.append(tool)

        return tools

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        tool = self._tools.get(tool_name)
        if not tool:
            return json.dumps({"error": f"MCP tool '{tool_name}' not found"})

        proc = self._processes.get(tool.server_name)
        if not proc or proc.returncode is not None:
            return json.dumps({"error": f"MCP server '{tool.server_name}' not connected"})

        original_name = tool_name.split("__", 1)[1] if "__" in tool_name else tool_name

        await self._send_jsonrpc(proc, "tools/call", {
            "name": original_name,
            "arguments": arguments,
        })
        response = await self._read_jsonrpc(proc)

        result = response.get("result", {})
        content_parts = result.get("content", [])
        text_parts = []
        for part in content_parts:
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        return "\n".join(text_parts) if text_parts else json.dumps(result)

    async def _send_jsonrpc(self, proc: asyncio.subprocess.Process, method: str, params: dict):
        self._request_id += 1
        message = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        data = json.dumps(message) + "\n"
        proc.stdin.write(data.encode())
        await proc.stdin.drain()

    async def _send_jsonrpc_notification(self, proc: asyncio.subprocess.Process, method: str, params: dict):
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        data = json.dumps(message) + "\n"
        proc.stdin.write(data.encode())
        await proc.stdin.drain()

    async def _read_jsonrpc(self, proc: asyncio.subprocess.Process, timeout: float = 30.0) -> dict:
        try:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            if not line:
                return {"error": "Server closed connection"}
            return json.loads(line.decode().strip())
        except asyncio.TimeoutError:
            return {"error": "Timeout waiting for MCP response"}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON from MCP server: {e}"}

    def get_all_tools(self) -> list[MCPTool]:
        return list(self._tools.values())

    def get_tool_schemas(self) -> list[dict]:
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": f"[MCP:{tool.server_name}] {tool.description}",
                    "parameters": tool.parameters,
                },
            })
        return schemas

    async def disconnect_all(self):
        for name, proc in self._processes.items():
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._processes.clear()
        self._tools.clear()
