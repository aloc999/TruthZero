import asyncio
import statistics
import time
from zer0code.tools.base import BaseTool, ToolResult


class TimingAttackTool(BaseTool):
    name = "timing_attack"
    description = "Measure response times to detect time-based blind SQLi, command injection, and other timing-based vulnerabilities."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL"},
            "param": {"type": "string", "description": "Parameter to test"},
            "baseline_value": {"type": "string", "description": "Normal/safe value for baseline", "default": "1"},
            "delay_payload": {"type": "string", "description": "Payload that should cause delay (e.g., ' OR SLEEP(5)--)"},
            "delay_seconds": {"type": "integer", "description": "Expected delay in seconds", "default": 5},
            "method": {"type": "string", "default": "GET"},
            "samples": {"type": "integer", "description": "Number of baseline samples", "default": 3},
            "headers": {"type": "object"},
            "cookies": {"type": "string"},
        },
        "required": ["url", "param", "delay_payload"],
    }

    async def execute(self, url: str = "", param: str = "", baseline_value: str = "1", delay_payload: str = "", delay_seconds: int = 5, method: str = "GET", samples: int = 3, headers: dict = None, cookies: str = "", **kwargs) -> ToolResult:
        import httpx
        try:
            req_headers = dict(headers or {})
            if cookies:
                req_headers["Cookie"] = cookies

            async def send_request(value):
                async with httpx.AsyncClient(timeout=max(delay_seconds + 15, 30), verify=False) as client:
                    if method.upper() == "GET":
                        sep = "&" if "?" in url else "?"
                        target = f"{url}{sep}{param}={value}"
                        start = time.monotonic()
                        resp = await client.get(target, headers=req_headers)
                        elapsed = time.monotonic() - start
                    else:
                        body = f"{param}={value}"
                        if not req_headers.get("Content-Type"):
                            req_headers["Content-Type"] = "application/x-www-form-urlencoded"
                        start = time.monotonic()
                        resp = await client.request(method, url, headers=req_headers, content=body)
                        elapsed = time.monotonic() - start
                    return elapsed, resp.status_code, len(resp.text)

            output = f"TIMING ANALYSIS\n{'─' * 60}\n\n"

            output += f"Baseline measurements ({samples} samples):\n"
            baseline_times = []
            for i in range(samples):
                elapsed, status, length = await send_request(baseline_value)
                baseline_times.append(elapsed)
                output += f"  Sample {i+1}: {elapsed:.3f}s (status: {status}, {length} bytes)\n"

            avg_baseline = statistics.mean(baseline_times)
            std_baseline = statistics.stdev(baseline_times) if len(baseline_times) > 1 else 0
            output += f"  Average: {avg_baseline:.3f}s (±{std_baseline:.3f}s)\n\n"

            output += f"Delay payload test:\n"
            output += f"  Payload: {delay_payload}\n"
            output += f"  Expected delay: {delay_seconds}s\n"
            delay_elapsed, delay_status, delay_length = await send_request(delay_payload)
            output += f"  Response time: {delay_elapsed:.3f}s (status: {delay_status}, {delay_length} bytes)\n\n"

            time_diff = delay_elapsed - avg_baseline
            threshold = delay_seconds * 0.7

            output += f"RESULT:\n"
            output += f"  Baseline avg: {avg_baseline:.3f}s\n"
            output += f"  Delay response: {delay_elapsed:.3f}s\n"
            output += f"  Difference: {time_diff:.3f}s\n"
            output += f"  Threshold: {threshold:.1f}s (70% of expected {delay_seconds}s)\n\n"

            if time_diff >= threshold:
                output += f"⚠️ TIME-BASED VULNERABILITY CONFIRMED\n"
                output += f"Response was {time_diff:.1f}s slower than baseline.\n"
                output += f"This strongly indicates time-based blind injection.\n"
            elif time_diff >= delay_seconds * 0.3:
                output += f"⚠️ POSSIBLE time-based vulnerability (inconclusive)\n"
                output += f"Response was {time_diff:.1f}s slower — retry with longer delay.\n"
            else:
                output += f"✓ No significant timing difference — likely not vulnerable.\n"

            return ToolResult(output=output, success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
