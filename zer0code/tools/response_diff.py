import asyncio
import difflib
import time
from zer0code.tools.base import BaseTool, ToolResult


class ResponseDiffTool(BaseTool):
    name = "response_diff"
    description = "Compare two HTTP responses to detect differences — useful for blind SQLi, boolean-based detection, and parameter tampering."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Base URL to test"},
            "param": {"type": "string", "description": "Parameter to modify"},
            "true_value": {"type": "string", "description": "Value that should return 'true' response (e.g., ' OR 1=1--)"},
            "false_value": {"type": "string", "description": "Value that should return 'false' response (e.g., ' OR 1=2--)"},
            "method": {"type": "string", "default": "GET"},
            "headers": {"type": "object"},
            "cookies": {"type": "string"},
        },
        "required": ["url", "param", "true_value", "false_value"],
    }

    async def execute(self, url: str = "", param: str = "", true_value: str = "", false_value: str = "", method: str = "GET", headers: dict = None, cookies: str = "", **kwargs) -> ToolResult:
        import httpx
        try:
            req_headers = dict(headers or {})
            if cookies:
                req_headers["Cookie"] = cookies

            async with httpx.AsyncClient(timeout=30, verify=False, follow_redirects=True) as client:
                if method.upper() == "GET":
                    sep = "&" if "?" in url else "?"
                    url_true = f"{url}{sep}{param}={true_value}"
                    url_false = f"{url}{sep}{param}={false_value}"
                    t1 = time.monotonic()
                    resp_true = await client.get(url_true, headers=req_headers)
                    time_true = time.monotonic() - t1
                    t2 = time.monotonic()
                    resp_false = await client.get(url_false, headers=req_headers)
                    time_false = time.monotonic() - t2
                else:
                    body_true = f"{param}={true_value}"
                    body_false = f"{param}={false_value}"
                    if not req_headers.get("Content-Type"):
                        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
                    t1 = time.monotonic()
                    resp_true = await client.request(method, url, headers=req_headers, content=body_true)
                    time_true = time.monotonic() - t1
                    t2 = time.monotonic()
                    resp_false = await client.request(method, url, headers=req_headers, content=body_false)
                    time_false = time.monotonic() - t2

            output = f"RESPONSE COMPARISON\n"
            output += f"{'─' * 60}\n"
            output += f"  TRUE  ({true_value}): {resp_true.status_code} | {len(resp_true.text)} bytes | {time_true:.3f}s\n"
            output += f"  FALSE ({false_value}): {resp_false.status_code} | {len(resp_false.text)} bytes | {time_false:.3f}s\n"
            output += f"{'─' * 60}\n\n"

            status_diff = resp_true.status_code != resp_false.status_code
            length_diff = abs(len(resp_true.text) - len(resp_false.text))
            time_diff = abs(time_true - time_false)
            content_diff = resp_true.text != resp_false.text

            output += f"ANALYSIS:\n"
            output += f"  Status code differs: {'YES ⚠️' if status_diff else 'no'}\n"
            output += f"  Content length diff: {length_diff} bytes {'⚠️' if length_diff > 10 else ''}\n"
            output += f"  Timing difference: {time_diff:.3f}s {'⚠️ POSSIBLE TIME-BASED' if time_diff > 3 else ''}\n"
            output += f"  Content differs: {'YES ⚠️' if content_diff else 'no'}\n\n"

            if status_diff or length_diff > 10 or content_diff:
                output += f"⚠️ DIFFERENCES DETECTED — possible blind vulnerability\n\n"
                if content_diff:
                    true_lines = resp_true.text[:2000].splitlines()
                    false_lines = resp_false.text[:2000].splitlines()
                    diff = list(difflib.unified_diff(false_lines, true_lines, lineterm="", n=2))
                    if diff:
                        output += f"DIFF (first differences):\n"
                        for line in diff[:30]:
                            output += f"  {line}\n"
            else:
                output += f"✓ No significant differences — likely not vulnerable via this parameter\n"

            return ToolResult(output=output, success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
