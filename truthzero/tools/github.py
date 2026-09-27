import asyncio

from truthzero.tools.base import BaseTool, ToolResult


class GitHubPRTool(BaseTool):
    name = "github_pr"
    description = "Create a GitHub Pull Request using the gh CLI."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "PR title"},
            "body": {"type": "string", "description": "PR description"},
            "base": {"type": "string", "description": "Base branch", "default": "main"},
            "draft": {"type": "boolean", "default": False},
            "path": {"type": "string", "description": "Repository path", "default": "."},
        },
        "required": ["title"],
    }

    async def execute(self, title: str = "", body: str = "", base: str = "main", draft: bool = False, path: str = ".", **kwargs) -> ToolResult:
        try:
            cmd = ["gh", "pr", "create", "--title", title, "--base", base]
            if body:
                cmd.extend(["--body", body])
            if draft:
                cmd.append("--draft")

            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=path
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = (stdout or b"").decode() + (stderr or b"").decode()

            if proc.returncode == 0:
                return ToolResult(output=output.strip(), success=True)
            return ToolResult(output="", success=False, error=output.strip())
        except FileNotFoundError:
            return ToolResult(output="", success=False, error="GitHub CLI (gh) not installed. Install: https://cli.github.com/")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))


class GitHubIssueTool(BaseTool):
    name = "github_issue"
    description = "Create a GitHub Issue using the gh CLI."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Issue title"},
            "body": {"type": "string", "description": "Issue description"},
            "labels": {"type": "string", "description": "Comma-separated labels"},
            "path": {"type": "string", "description": "Repository path", "default": "."},
        },
        "required": ["title"],
    }

    async def execute(self, title: str = "", body: str = "", labels: str = "", path: str = ".", **kwargs) -> ToolResult:
        try:
            cmd = ["gh", "issue", "create", "--title", title]
            if body:
                cmd.extend(["--body", body])
            if labels:
                cmd.extend(["--label", labels])

            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=path
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = (stdout or b"").decode() + (stderr or b"").decode()

            if proc.returncode == 0:
                return ToolResult(output=output.strip(), success=True)
            return ToolResult(output="", success=False, error=output.strip())
        except FileNotFoundError:
            return ToolResult(output="", success=False, error="GitHub CLI (gh) not installed")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
