import re

import httpx

from truthzero.tools.base import BaseTool, ToolResult

MAX_RESPONSE_SIZE = 100000


def html_to_markdown(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h4[^>]*>(.*?)</h4>", r"\n#### \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h5[^>]*>(.*?)</h5>", r"\n##### \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h6[^>]*>(.*?)</h6>", r"\n###### \1\n", text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(
        r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>',
        r"[\2](\1)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    text = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<b[^>]*>(.*?)</b>", r"**\1**", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.DOTALL | re.IGNORECASE)

    text = re.sub(
        r"<pre[^>]*>(.*?)</pre>", r"\n```\n\1\n```\n", text, flags=re.DOTALL | re.IGNORECASE
    )

    text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<hr[^>]*/?>", "\n---\n", text, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"&nbsp;", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_tags(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = "Fetch content from a URL and return it in the specified format"
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
            "format": {
                "type": "string",
                "enum": ["text", "markdown", "html"],
                "description": "Output format",
                "default": "markdown",
            },
        },
        "required": ["url"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "")
        fmt = kwargs.get("format", "markdown")

        if not url:
            return ToolResult(output="", success=False, error="No URL provided")

        if url.startswith("http://"):
            url = "https://" + url[7:]
        elif not url.startswith("https://"):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; TRUTHZERO/1.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                content = response.text

                if fmt == "html":
                    output = content
                elif fmt == "text":
                    output = strip_tags(content)
                else:
                    content_type = response.headers.get("content-type", "")
                    if "text/html" in content_type or "application/xhtml" in content_type:
                        output = html_to_markdown(content)
                    else:
                        output = content

                if len(output) > MAX_RESPONSE_SIZE:
                    output = (
                        output[:MAX_RESPONSE_SIZE]
                        + f"\n\n... [TRUNCATED at {MAX_RESPONSE_SIZE} characters]"
                    )

                return ToolResult(output=output, success=True)

        except httpx.TimeoutException:
            return ToolResult(output="", success=False, error=f"Request timed out: {url}")
        except httpx.HTTPStatusError as e:
            return ToolResult(
                output="", success=False, error=f"HTTP {e.response.status_code}: {url}"
            )
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Fetch failed: {e}")
