import os
from typing import Optional, AsyncGenerator

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.prompt import Confirm

from truthzero.ui.themes import Theme, THEMES
from truthzero.ui.components import (
    Banner,
    ToolPanel,
    MemoryPanel,
    StatusBar,
    ResponseRenderer,
)


class TerminalUI:
    def __init__(self, config: Optional[dict] = None, theme_name: str = "hacker"):
        self.config = config or {}
        self.theme = THEMES.get(theme_name, THEMES["hacker"])
        self.console = Console()
        self.banner = Banner(
            self.theme,
            provider=self.config.get("provider", ""),
            model=self.config.get("model", ""),
        )
        self.tool_panel = ToolPanel(self.theme)
        self.memory_panel = MemoryPanel(self.theme)
        self.status_bar = StatusBar(self.theme)
        self.response_renderer = ResponseRenderer(self.theme)

    def show_banner(self) -> None:
        self.banner.render(self.console)

    def show_welcome(self) -> None:
        help_text = Text()
        help_text.append("\n  Quick Start\n", style=self.theme.primary)
        help_text.append("  Type naturally to interact. ", style=self.theme.fg)
        help_text.append("Available commands:\n\n", style=self.theme.fg)

        commands = [
            ("/help", "Show all commands"),
            ("/tools", "List available tools"),
            ("/memory", "View learned memories"),
            ("/theme <name>", "Switch theme (hacker/dark/minimal)"),
            ("/clear", "Clear screen"),
            ("/exit", "Exit TRUTHZERO"),
        ]

        for cmd, desc in commands:
            help_text.append(f"  {cmd:<20}", style=self.theme.accent)
            help_text.append(f"{desc}\n", style=self.theme.muted)

        help_text.append("")
        self.console.print(help_text)

    def render_response(self, text: str) -> None:
        self.console.print()
        self.response_renderer.render_markdown(self.console, text)
        self.console.print()

    async def render_stream(self, token_generator: AsyncGenerator[str, None]) -> str:
        self.console.print()
        result = await self.response_renderer.render_stream(
            self.console, token_generator
        )
        self.console.print()
        return result

    def render_tool_call(self, name: str, args: dict) -> None:
        self.console.print()
        self.tool_panel.render_call(self.console, name, args)

    def render_tool_result(
        self, name: str, result: str, success: bool = True
    ) -> None:
        self.tool_panel.render_result(self.console, name, result, success)

    def render_error(self, error: str) -> None:
        error_text = Text()
        error_text.append(" \u2717 Error: ", style=self.theme.error)
        error_text.append(error, style=self.theme.fg)

        panel = Panel(
            error_text,
            border_style=self.theme.error,
            title=Text("Error", style=self.theme.error),
            title_align="left",
            padding=(0, 1),
        )
        self.console.print(panel)

    def show_status(
        self,
        model: str = "",
        provider: str = "",
        tokens: int = 0,
        memories: int = 0,
    ) -> None:
        self.status_bar.render(
            self.console,
            model=model,
            provider=provider,
            tokens=tokens,
            memories=memories,
        )

    def show_help(self) -> None:
        table = Table(
            border_style=self.theme.border,
            show_header=True,
            header_style=self.theme.primary,
            padding=(0, 2),
            expand=True,
            title=Text("TRUTHZERO Commands", style=self.theme.primary),
        )
        table.add_column("Command", style=self.theme.accent, width=24)
        table.add_column("Description", style=self.theme.fg)
        table.add_column("Example", style=self.theme.muted)

        commands = [
            ("/help", "Show this help panel", "/help"),
            ("/tools", "List all available tools", "/tools"),
            ("/memory", "Show learned memories", "/memory"),
            ("/memory add <text>", "Add a manual memory", '/memory add target uses nginx'),
            ("/theme <name>", "Switch UI theme", "/theme dark"),
            ("/model <name>", "Switch AI model", "/model gpt-4"),
            ("/clear", "Clear the screen", "/clear"),
            ("/status", "Show current status", "/status"),
            ("/history", "Show conversation history", "/history"),
            ("/export", "Export session to file", "/export report.md"),
            ("/exit", "Exit TRUTHZERO", "/exit"),
        ]

        for cmd, desc, example in commands:
            table.add_row(cmd, desc, example)

        panel = Panel(
            table,
            border_style=self.theme.border,
            padding=(1, 1),
        )
        self.console.print(panel)

    def show_tools(self, tools: list[dict]) -> None:
        table = Table(
            border_style=self.theme.border,
            show_header=True,
            header_style=self.theme.primary,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("Tool", style=self.theme.tool_name, width=22)
        table.add_column("Description", style=self.theme.fg)
        table.add_column("Risk", style=self.theme.warning, width=10)

        for tool in tools:
            risk = tool.get("risk", "low")
            risk_style = self.theme.success
            if risk == "high":
                risk_style = self.theme.error
            elif risk == "medium":
                risk_style = self.theme.warning

            table.add_row(
                tool.get("name", "unknown"),
                tool.get("description", ""),
                Text(risk, style=risk_style),
            )

        panel = Panel(
            table,
            border_style=self.theme.border,
            title=Text("\U0001f527 Available Tools", style=self.theme.primary),
            title_align="left",
            padding=(0, 0),
        )
        self.console.print(panel)

    def show_memories(self, memories: list[dict]) -> None:
        self.memory_panel.render(self.console, memories)

    def confirm(self, prompt: str) -> bool:
        confirm_text = Text()
        confirm_text.append(" ? ", style=self.theme.warning)
        confirm_text.append(prompt, style=self.theme.fg)
        self.console.print(confirm_text)
        return Confirm.ask(
            Text("  Continue?", style=self.theme.accent),
            console=self.console,
            default=False,
        )

    def set_theme(self, theme_name: str) -> bool:
        if theme_name in THEMES:
            self.theme = THEMES[theme_name]
            self.banner = Banner(
                self.theme,
                provider=self.config.get("provider", ""),
                model=self.config.get("model", ""),
            )
            self.tool_panel = ToolPanel(self.theme)
            self.memory_panel = MemoryPanel(self.theme)
            self.status_bar = StatusBar(self.theme)
            self.response_renderer = ResponseRenderer(self.theme)
            self.console.print(
                Text(
                    f"  Theme switched to '{theme_name}'",
                    style=self.theme.success,
                )
            )
            return True
        self.console.print(
            Text(
                f"  Unknown theme '{theme_name}'. Available: {', '.join(THEMES.keys())}",
                style=self.theme.error,
            )
        )
        return False

    def clear(self) -> None:
        self.console.clear()
