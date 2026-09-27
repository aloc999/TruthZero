import asyncio
import re
from urllib.parse import urljoin, urlparse

from truthzero.tools.base import BaseTool, ToolResult


class CrawlerTool(BaseTool):
    name = "web_crawl"
    description = "Crawl a website and extract all URLs, endpoints, forms, and parameters. Like katana/gospider."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Target URL to crawl"},
            "depth": {"type": "integer", "description": "Max crawl depth", "default": 3},
            "max_pages": {"type": "integer", "description": "Max pages to visit", "default": 100},
            "same_domain": {"type": "boolean", "description": "Stay on same domain", "default": True},
        },
        "required": ["url"],
    }

    async def execute(self, url: str = "", depth: int = 3, max_pages: int = 100, same_domain: bool = True, **kwargs) -> ToolResult:
        katana = await self._try_katana(url, depth, max_pages)
        if katana:
            return katana

        try:
            import httpx
        except ImportError:
            return ToolResult(output="", success=False, error="httpx required for crawling")

        try:
            parsed_base = urlparse(url)
            base_domain = parsed_base.netloc
            visited = set()
            queue = [(url, 0)]
            found_urls = set()
            found_params = set()
            found_forms = set()

            async with httpx.AsyncClient(timeout=15, verify=False, follow_redirects=True) as client:
                while queue and len(visited) < max_pages:
                    current_url, current_depth = queue.pop(0)
                    if current_url in visited or current_depth > depth:
                        continue
                    visited.add(current_url)

                    try:
                        resp = await client.get(current_url)
                        body = resp.text
                    except Exception:
                        continue

                    links = re.findall(r'(?:href|src|action)=["\']([^"\']+)', body)
                    for link in links:
                        full_url = urljoin(current_url, link)
                        parsed = urlparse(full_url)
                        if same_domain and parsed.netloc != base_domain:
                            continue
                        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if parsed.query:
                            found_params.add(f"{parsed.path}?{parsed.query}")
                        found_urls.add(clean)
                        if clean not in visited:
                            queue.append((clean, current_depth + 1))

                    forms = re.findall(r'<form[^>]*action=["\']([^"\']*)["\'][^>]*>(.*?)</form>', body, re.DOTALL | re.IGNORECASE)
                    for action, form_body in forms:
                        full_action = urljoin(current_url, action) if action else current_url
                        inputs = re.findall(r'<input[^>]*name=["\']([^"\']+)', form_body, re.IGNORECASE)
                        found_forms.add(f"{full_action} params=[{','.join(inputs)}]")

            results = []
            results.append(f"CRAWL RESULTS for {url}")
            results.append(f"Pages visited: {len(visited)}")
            results.append("")

            if found_urls:
                results.append(f"URLS ({len(found_urls)}):")
                for u in sorted(found_urls)[:200]:
                    results.append(f"  {u}")
                results.append("")

            if found_params:
                results.append(f"PARAMETERIZED URLS ({len(found_params)}):")
                for p in sorted(found_params)[:100]:
                    results.append(f"  {p}")
                results.append("")

            if found_forms:
                results.append(f"FORMS ({len(found_forms)}):")
                for f in sorted(found_forms)[:50]:
                    results.append(f"  {f}")

            return ToolResult(output="\n".join(results), success=True)
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

    async def _try_katana(self, url: str, depth: int, max_pages: int) -> ToolResult | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "katana", "-u", url, "-d", str(depth), "-jc", "-silent",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0 and stdout:
                urls = stdout.decode().strip().split("\n")
                output = f"KATANA CRAWL ({len(urls)} URLs):\n" + "\n".join(f"  {u}" for u in urls[:max_pages])
                return ToolResult(output=output, success=True)
        except (FileNotFoundError, asyncio.TimeoutError):
            pass
        return None
