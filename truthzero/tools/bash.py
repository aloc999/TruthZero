import asyncio
import os

from truthzero.tools.base import BaseTool, ToolResult

DANGEROUS_PATTERNS = [
    "rm -rf /",
    "mkfs.",
    "dd if=/dev/zero",
    ":(){:|:&};:",
    "> /dev/sda",
]


class BashTool(BaseTool):
    name = "bash"
    description = "Execute a bash command and return output"
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
            },
            "workdir": {
                "type": "string",
                "description": "Working directory for the command",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 120,
            },
        },
        "required": ["command"],
    }

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs.get("command", "")
        workdir = kwargs.get("workdir", None)
        timeout = kwargs.get("timeout", 120)

        if not command:
            return ToolResult(output="", success=False, error="No command provided")

        warnings = []
        for pattern in DANGEROUS_PATTERNS:
            if pattern in command:
                warnings.append(f"WARNING: Potentially dangerous pattern detected: {pattern}")

        if workdir and not os.path.isdir(workdir):
            return ToolResult(
                output="", success=False, error=f"Working directory does not exist: {workdir}"
            )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    output="",
                    success=False,
                    error=f"Command timed out after {timeout} seconds",
                )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            output_parts = []
            if warnings:
                output_parts.append("\n".join(warnings))
            if stdout_str:
                output_parts.append(stdout_str)
            if stderr_str:
                output_parts.append(stderr_str)

            output = "\n".join(output_parts)

            if len(output) > 50000:
                output = (
                    output[:20000]
                    + f"\n\n... [TRUNCATED {len(output) - 40000} characters] ...\n\n"
                    + output[-20000:]
                )

            return ToolResult(
                output=output,
                success=process.returncode == 0,
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
            )

        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))
