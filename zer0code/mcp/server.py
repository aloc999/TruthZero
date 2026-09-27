"""ZER0CODE MCP server — stdio JSON-RPC for Claude Desktop / Cursor.

Exposes swarm capabilities as MCP tools:
- blackboard_write / blackboard_hot / blackboard_summary
- playbook_list / playbook_get / chain_list / chain_get
- cvss_score / adaptive_rank (stateless helpers)
- burp_status (bridge probe)

Run: `zer0code mcp serve`. Beta: tool set grows in Wave 2+.
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _tool_defs() -> list[dict]:
    return [
        {"name": "blackboard_write",
         "description": "Write a finding to the swarm blackboard",
         "inputSchema": {"type": "object", "properties": {
             "ftype": {"type": "string"}, "title": {"type": "string"},
             "detail": {"type": "string"}, "severity": {"type": "string"},
             "target": {"type": "string"}}, "required": ["ftype", "title"]}},
        {"name": "blackboard_hot",
         "description": "List hot (non-decayed) blackboard findings",
         "inputSchema": {"type": "object", "properties": {
             "threshold": {"type": "number"}, "board_file": {"type": "string"}}}},
        {"name": "blackboard_summary",
         "description": "Summary counts of the blackboard",
         "inputSchema": {"type": "object", "properties": {
             "board_file": {"type": "string"}}}},
        {"name": "playbook_list",
         "description": "List available swarm playbooks",
         "inputSchema": {"type": "object", "properties": {}}},
        {"name": "playbook_get",
         "description": "Get a playbook's steps",
         "inputSchema": {"type": "object", "properties": {
             "name": {"type": "string"}}, "required": ["name"]}},
        {"name": "chain_list",
         "description": "List exploit chains",
         "inputSchema": {"type": "object", "properties": {}}},
        {"name": "chain_get",
         "description": "Get an exploit chain definition",
         "inputSchema": {"type": "object", "properties": {
             "name": {"type": "string"}}, "required": ["name"]}},
        {"name": "cvss_score",
         "description": "Score a CVSS 3.1 vector",
         "inputSchema": {"type": "object", "properties": {
             "vector": {"type": "string"}}, "required": ["vector"]}},
        {"name": "burp_status",
         "description": "Probe Burp REST API bridge status",
         "inputSchema": {"type": "object", "properties": {
             "base_url": {"type": "string"}}}},
    ]


def _call(name: str, args: dict) -> str:
    try:
        if name in ("blackboard_write", "blackboard_hot", "blackboard_summary"):
            from zer0code.swarm import Blackboard
            board = Blackboard(args.get("board_file") or None)
            if name == "blackboard_write":
                fid = board.add(args.get("ftype", "NOTE"), args.get("title", ""),
                                detail=args.get("detail", ""),
                                severity=args.get("severity", "info"),
                                target=args.get("target", ""))
                return json.dumps({"finding_id": fid})
            if name == "blackboard_hot":
                hot = board.hot(float(args.get("threshold", 0.2)))
                return json.dumps([f.to_dict() for f in hot[:20]], indent=2)
            return json.dumps(board.summary(), indent=2)
        if name in ("playbook_list", "playbook_get", "chain_list", "chain_get"):
            from zer0code import playbooks as pb
            if name == "playbook_list":
                return json.dumps(pb.list_playbooks())
            if name == "chain_list":
                return json.dumps(pb.list_chains())
            if name == "playbook_get":
                return json.dumps(pb.load_playbook(args["name"]), indent=2)
            return json.dumps(pb.load_chain(args["name"]), indent=2)
        if name == "cvss_score":
            from zer0code.scoring import cvss31_score
            score, sev = cvss31_score(args["vector"])
            return json.dumps({"score": score, "severity": sev})
        if name == "burp_status":
            import asyncio
            from zer0code.tools.burp_bridge import BurpBridgeTool
            res = asyncio.run(BurpBridgeTool().execute(
                action="status", base_url=args.get("base_url", "")))
            return json.dumps({"success": res.success,
                               "output": res.output or res.error})
        return json.dumps({"error": f"unknown tool: {name}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _text_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def serve() -> None:
    """Blocking stdio loop. Each line = one JSON-RPC message."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params", {}) or {}

        def reply(result: Any) -> None:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
            sys.stdout.flush()

        if method == "initialize":
            reply({"protocolVersion": "2024-11-05",
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "zer0code", "version": "0.9.0"}})
        elif method == "notifications/initialized":
            continue  # notification, no reply
        elif method == "tools/list":
            reply({"tools": _tool_defs()})
        elif method == "tools/call":
            out = _call(params.get("name", ""), params.get("arguments", {}) or {})
            reply(_text_result(out))
        elif method == "ping":
            reply({})
        else:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": mid,
                 "error": {"code": -32601, "message": "Method not found"}}) + "\n")
            sys.stdout.flush()
