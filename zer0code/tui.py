import os
import shutil
from typing import Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.table import Table


MIN_WIDTH = 60
MIN_HEIGHT = 15

BANNER = "[bold cyan]ZER0CODE[/] [dim]// AI Agent Framework[/dim]"


class FullScreenTUI:
    def __init__(self, show_tool_panel: bool = False):
        self.console = Console()
        self._live: Optional[Live] = None
        self._show_tool_panel = show_tool_panel
        self._conversation: list[str] = []
        self._status_text = "Ready"
        self._tool_content = ""
        self._input_hint = "[dim]Type your prompt below...[/dim]"
        self._layout = self._build_layout()

    def _check_terminal_size(self) -> bool:
        size = shutil.get_terminal_size((80, 24))
        return size.columns >= MIN_WIDTH and size.lines >= MIN_HEIGHT

    def _build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )
        if self._show_tool_panel:
            layout["body"].split_row(
                Layout(name="conversation", ratio=2),
                Layout(name="tools", ratio=1),
            )
        else:
            layout["body"].split_row(
                Layout(name="conversation"),
            )
        return layout

    def _render_header(self) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(justify="right")
        table.add_row(BANNER, f"[green]● {self._status_text}[/]")
        return Panel(table, style="bold blue")

    def _render_conversation(self) -> Panel:
        if not self._conversation:
            content = Text("No messages yet.", style="dim")
        else:
            lines = self._conversation[-50:]
            content = Text("\n".join(lines))
        return Panel(content, title="[bold]Conversation[/]", border_style="cyan")

    def _render_tool_panel(self) -> Panel:
        content = Text(self._tool_content or "No tool output.", style="dim")
        return Panel(content, title="[bold]Tools / Preview[/]", border_style="yellow")

    def _render_footer(self) -> Panel:
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(justify="right")
        table.add_row(self._input_hint, "[dim]Ctrl+C to exit[/dim]")
        return Panel(table, title="[bold]Input[/]", border_style="green")

    def _refresh(self):
        self._layout["header"].update(self._render_header())
        self._layout["conversation"].update(self._render_conversation())
        if self._show_tool_panel and "tools" in self._layout:
            self._layout["tools"].update(self._render_tool_panel())
        self._layout["footer"].update(self._render_footer())

    def start(self):
        if not self._check_terminal_size():
            self.console.print("[yellow]Terminal too small for TUI mode. Need {}x{}.[/]".format(MIN_WIDTH, MIN_HEIGHT))
            return False
        self._refresh()
        self._live = Live(
            self._layout,
            console=self.console,
            refresh_per_second=4,
            screen=True,
        )
        self._live.start()
        return True

    def stop(self):
        if self._live:
            self._live.stop()
            self._live = None

    def update_conversation(self, role: str, message: str):
        prefix = {"user": "▶ You", "assistant": "◀ Agent", "system": "● System"}.get(role, role)
        self._conversation.append(f"[bold]{prefix}:[/bold] {message}")
        self._refresh()
        if self._live:
            self._live.update(self._layout)

    def update_status(self, status: str):
        self._status_text = status
        self._refresh()
        if self._live:
            self._live.update(self._layout)

    def update_tool_panel(self, content: str):
        self._tool_content = content
        if self._show_tool_panel:
            self._refresh()
            if self._live:
                self._live.update(self._layout)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
