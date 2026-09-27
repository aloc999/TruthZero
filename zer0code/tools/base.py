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

    @classmethod
    def schema(cls) -> dict:
        """OpenAI function-calling schema for this tool."""
        params = getattr(cls, "parameters", None)
        if not isinstance(params, dict):
            # BaseTool itself stores a dataclasses.Field placeholder.
            params = {"type": "object", "properties": {}}
        return {
            "type": "function",
            "function": {
                "name": getattr(cls, "name", ""),
                "description": getattr(cls, "description", ""),
                "parameters": params,
            },
        }
