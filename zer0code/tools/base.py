from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolResult:
    output: str = ""
    success: bool = True
    error: Optional[str] = None


class BaseTool:
    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)

    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError
