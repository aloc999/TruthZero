from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    output: str = ""
    success: bool = True
    error: str | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    @classmethod
    def schema(cls) -> dict:
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.parameters,
            },
        }

    @classmethod
    def anthropic_schema(cls) -> dict:
        return {
            "name": cls.name,
            "description": cls.description,
            "input_schema": cls.parameters,
        }
