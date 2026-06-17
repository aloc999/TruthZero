import asyncio

from zer0code.tools.base import BaseTool, ToolResult


class GitStatusTool(BaseTool):
    name = "git_status"
    description = "Show git repository status"
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Repository path"},
        },
        "required": [],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        try:
            status_proc = await asyncio.create_subprocess_exec(
                "git", "status", "--porcelain",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            status_stdout, status_stderr = await status_proc.communicate()

            branch_proc = await asyncio.create_subprocess_exec(
                "git", "branch", "--show-current",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            branch_stdout, branch_stderr = await branch_proc.communicate()

            if status_proc.returncode != 0:
                return ToolResult(
                    success=False,
                    output=status_stderr.decode().strip(),
                )

            branch = branch_stdout.decode().strip()
            status = status_stdout.decode().strip()

            result = f"Branch: {branch}\n"
            if status:
                result += f"\n{status}"
            else:
                result += "\nWorking tree clean"

            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, output=str(e))


class GitDiffTool(BaseTool):
    name = "git_diff"
    description = "Show git diff for staged or unstaged changes"
    parameters = {
        "type": "object",
        "properties": {
            "staged": {"type": "boolean", "description": "Show staged changes"},
            "file": {"type": "string", "description": "Specific file to diff"},
            "path": {"type": "string"},
        },
        "required": [],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        staged = kwargs.get("staged", False)
        file = kwargs.get("file")

        try:
            cmd = ["git", "diff"]
            if staged:
                cmd.append("--cached")
            if file:
                cmd.extend(["--", file])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return ToolResult(success=False, output=stderr.decode().strip())

            output = stdout.decode().strip()
            if not output:
                output = "No changes"

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output=str(e))


class GitCommitTool(BaseTool):
    name = "git_commit"
    description = "Stage files and create a git commit"
    parameters = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message"},
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files to stage (empty = all)",
            },
            "path": {"type": "string"},
        },
        "required": ["message"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        message = kwargs["message"]
        files = kwargs.get("files", [])

        try:
            if files:
                add_cmd = ["git", "add", "--"] + files
            else:
                add_cmd = ["git", "add", "-A"]

            add_proc = await asyncio.create_subprocess_exec(
                *add_cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            add_stdout, add_stderr = await add_proc.communicate()

            if add_proc.returncode != 0:
                return ToolResult(success=False, output=add_stderr.decode().strip())

            commit_proc = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", message,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            commit_stdout, commit_stderr = await commit_proc.communicate()

            if commit_proc.returncode != 0:
                return ToolResult(
                    success=False, output=commit_stderr.decode().strip()
                )

            return ToolResult(success=True, output=commit_stdout.decode().strip())
        except Exception as e:
            return ToolResult(success=False, output=str(e))


class GitLogTool(BaseTool):
    name = "git_log"
    description = "Show git commit history"
    parameters = {
        "type": "object",
        "properties": {
            "count": {
                "type": "integer",
                "description": "Number of commits",
                "default": 10,
            },
            "oneline": {"type": "boolean", "default": True},
            "path": {"type": "string"},
        },
        "required": [],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        count = kwargs.get("count", 10)
        oneline = kwargs.get("oneline", True)

        try:
            cmd = ["git", "log"]
            if oneline:
                cmd.append("--oneline")
            cmd.append(f"-{count}")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return ToolResult(success=False, output=stderr.decode().strip())

            output = stdout.decode().strip()
            if not output:
                output = "No commits found"

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output=str(e))


class GitBranchTool(BaseTool):
    name = "git_branch"
    description = "List, create, or switch git branches"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "switch"],
                "default": "list",
            },
            "name": {"type": "string", "description": "Branch name for create/switch"},
            "path": {"type": "string"},
        },
        "required": [],
    }

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", ".")
        action = kwargs.get("action", "list")
        name = kwargs.get("name")

        try:
            if action == "list":
                cmd = ["git", "branch", "-a"]
            elif action == "create":
                if not name:
                    return ToolResult(
                        success=False, output="Branch name is required for create"
                    )
                cmd = ["git", "branch", name]
            elif action == "switch":
                if not name:
                    return ToolResult(
                        success=False, output="Branch name is required for switch"
                    )
                cmd = ["git", "checkout", name]
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                return ToolResult(success=False, output=stderr.decode().strip())

            output = stdout.decode().strip()
            if not output and action in ("create", "switch"):
                output = stderr.decode().strip()
            if not output:
                output = "No branches found"

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output=str(e))
