import asyncio
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from zer0code.tools.base import BaseTool, ToolResult


class BurpImportTool(BaseTool):
    name = "burp_import"
    description = "Import HTTP requests from Burp Suite XML export or Caido export file"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Path to Burp XML export or Caido JSON export"},
            "filter_status": {"type": "integer", "description": "Filter by response status code"},
            "filter_path": {"type": "string", "description": "Filter by URL path pattern"},
            "limit": {"type": "integer", "default": 50},
        },
        "required": ["file_path"],
    }

    async def execute(self, file_path: str = "", filter_status: int = 0, filter_path: str = "", limit: int = 50, **kwargs) -> ToolResult:
        path = Path(file_path).expanduser()
        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {file_path}")

        try:
            content = path.read_text(errors="ignore")
            if content.strip().startswith("<?xml") or content.strip().startswith("<items"):
                return await self._parse_burp_xml(path, filter_status, filter_path, limit)
            elif content.strip().startswith("[") or content.strip().startswith("{"):
                return await self._parse_json(path, filter_status, filter_path, limit)
            else:
                return ToolResult(output="", success=False, error="Unsupported format. Use Burp XML export or JSON.")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

    async def _parse_burp_xml(self, path: Path, filter_status: int, filter_path: str, limit: int) -> ToolResult:
        tree = ET.parse(str(path))
        root = tree.getroot()
        items = root.findall(".//item")
        results = []
        for item in items[:limit * 2]:
            url = item.findtext("url", "")
            method = item.findtext("method", "GET")
            status = item.findtext("status", "0")
            length = item.findtext("responselength", "0")
            mimetype = item.findtext("mimetype", "")

            if filter_status and str(filter_status) != status:
                continue
            if filter_path and filter_path.lower() not in url.lower():
                continue

            results.append(f"  {method:<6} {status:<4} {length:>8}B  {mimetype:<20} {url}")
            if len(results) >= limit:
                break

        if not results:
            return ToolResult(output="No matching requests found.", success=True)

        header = f"  {'Method':<6} {'Code':<4} {'Size':>8}   {'Type':<20} URL\n"
        header += "  " + "-" * 80 + "\n"
        return ToolResult(output=header + "\n".join(results) + f"\n\n  {len(results)} requests", success=True)

    async def _parse_json(self, path: Path, filter_status: int, filter_path: str, limit: int) -> ToolResult:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            data = data.get("requests", data.get("items", [data]))
        results = []
        for item in data[:limit]:
            url = item.get("url", item.get("URL", ""))
            method = item.get("method", "GET")
            status = str(item.get("status", item.get("statusCode", "")))
            if filter_status and str(filter_status) != status:
                continue
            if filter_path and filter_path.lower() not in url.lower():
                continue
            results.append(f"  {method:<6} {status:<4} {url}")

        if not results:
            return ToolResult(output="No matching requests found.", success=True)
        return ToolResult(output="\n".join(results) + f"\n\n  {len(results)} requests", success=True)


class BurpExportTool(BaseTool):
    name = "burp_export"
    description = "Export current findings and tested URLs to a JSON file for Burp Suite / Caido import"
    parameters = {
        "type": "object",
        "properties": {
            "output_path": {"type": "string", "description": "Output file path", "default": "zer0code-findings.json"},
            "format": {"type": "string", "enum": ["json", "csv", "markdown"], "default": "json"},
        },
        "required": [],
    }

    async def execute(self, output_path: str = "zer0code-findings.json", format: str = "json", **kwargs) -> ToolResult:
        findings = {
            "tool": "ZER0CODE",
            "export_type": format,
            "requests": [],
            "findings": [],
        }
        path = Path(output_path)
        path.write_text(json.dumps(findings, indent=2))
        return ToolResult(output=f"Exported to {output_path}", success=True)
