import asyncio
import os
import time
from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.css.query import NoMatches
    from textual.widgets import Footer, Header, Input, RichLog, Static
    from textual.reactive import reactive
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from rich.markdown import Markdown
from rich.text import Text
from rich.panel import Panel


BANNER_COMPACT = "ZER0CODE"


class StatusBar(Static):
    tokens = reactive(0)
    cost = reactive("$0.00")
    context_pct = reactive(0)
    session_id = reactive("")
    model = reactive("")
    provider = reactive("")

    def render(self) -> Text:
        bar = Text()
        bar.append(" ⚡ ", style="bold yellow")
        bar.append(f"{self.provider}", style="bold green")
        bar.append("/", style="dim")
        bar.append(f"{self.model}", style="bold green")
        bar.append("  │  ", style="dim")
        bar.append(f"tokens: {self.tokens:,}", style="cyan")
        bar.append("  │  ", style="dim")
        bar.append(f"{self.cost}", style="cyan")
        bar.append("  │  ", style="dim")
        bar.append(f"ctx: {self.context_pct}%", style="yellow" if self.context_pct > 75 else "cyan")
        bar.append("  │  ", style="dim")
        bar.append(f"session: {self.session_id[:8]}", style="dim")
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        bar.append("  │  ", style="dim")
        bar.append(cwd, style="dim")
        return bar


class ConversationLog(RichLog):
    pass


class ToolOutputLog(RichLog):
    pass


class ZeroCodeTUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    #header-bar {
        dock: top;
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }

    #main-container {
        height: 1fr;
    }

    #conversation {
        width: 2fr;
        border-right: solid $primary;
    }

    #side-panel {
        width: 1fr;
        display: block;
    }

    #side-panel.hidden {
        display: none;
    }

    #conversation.full {
        width: 1fr;
    }

    #input-area {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
    }

    Input {
        border: none;
    }

    RichLog {
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+b", "toggle_panel", "Toggle Panel"),
        Binding("ctrl+l", "clear_log", "Clear"),
        Binding("ctrl+d", "quit", "Exit"),
        Binding("ctrl+t", "toggle_theme", "Theme"),
    ]

    show_panel = reactive(True)

    def __init__(self, agent=None, config=None, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent
        self.config = config
        self._processing = False
        self.title = BANNER_COMPACT

    def compose(self) -> ComposeResult:
        yield Static(self._render_header(), id="header-bar")

        with Horizontal(id="main-container"):
            yield ConversationLog(id="conversation", wrap=True, highlight=True, markup=True)
            yield ToolOutputLog(id="side-panel", wrap=True, highlight=True, markup=True)

        yield Input(placeholder="Type a message or /help for commands...", id="input-area")
        yield StatusBar(id="status-bar")

    def _render_header(self) -> Text:
        header = Text()
        header.append("  ⚡ ZER0CODE ", style="bold green")
        header.append("│ ", style="dim")
        if self.config:
            header.append(f"{self.config.provider}/{self.config.model} ", style="bold cyan")
        header.append("│ ", style="dim")
        header.append("OPERATIONAL ", style="bold green")
        return header

    def on_mount(self) -> None:
        conv = self.query_one("#conversation", ConversationLog)
        conv.write(Text("  Welcome to ZER0CODE", style="bold green"))
        conv.write(Text("  Type a message to start. Press Ctrl+B to toggle side panel.\n", style="dim"))

        tools_panel = self.query_one("#side-panel", ToolOutputLog)
        tools_panel.write(Text("  Tool Output", style="bold magenta"))
        tools_panel.write(Text("  Tool results will appear here.\n", style="dim"))

        self._update_status()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return

        input_widget = self.query_one("#input-area", Input)
        input_widget.value = ""

        conv = self.query_one("#conversation", ConversationLog)

        if user_input.startswith("/"):
            await self._handle_command(user_input, conv)
            return

        conv.write(Text(f"\n  You: {user_input}", style="bold white"))

        if not self.agent:
            conv.write(Text("  Agent not initialized.", style="red"))
            return

        self._processing = True
        conv.write(Text("  Thinking...", style="dim"))

        def on_tool_call(name, args):
            tools_panel = self.query_one("#side-panel", ToolOutputLog)
            tools_panel.write(Text(f"\n  ▶ {name}", style="bold magenta"))
            for k, v in args.items():
                val = str(v)[:100]
                tools_panel.write(Text(f"    {k}={val}", style="dim"))

        def on_tool_result(name, result, hook_msgs=None):
            tools_panel = self.query_one("#side-panel", ToolOutputLog)
            status = "✓" if result.success else "✗"
            style = "green" if result.success else "red"
            tools_panel.write(Text(f"  {status} {name}", style=style))
            output = result.output if result.success else (result.error or "Error")
            if len(output) > 500:
                output = output[:500] + "..."
            tools_panel.write(Text(f"    {output}", style="dim"))

        self.agent.set_callbacks(on_tool_call=on_tool_call, on_tool_result=on_tool_result)

        try:
            response = await self.agent.run(user_input)
            if response:
                try:
                    conv.write(Markdown(response))
                except Exception:
                    conv.write(Text(f"  {response}", style="green"))
        except Exception as e:
            conv.write(Text(f"  Error: {e}", style="bold red"))
        finally:
            self._processing = False
            self._update_status()

    async def _handle_command(self, cmd: str, conv: ConversationLog):
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            help_text = Text()
            commands = [
                ("/help", "Show this help"),
                ("/clear", "Clear conversation"),
                ("/tools", "List tools"),
                ("/status", "Show status"),
                ("/exit", "Exit ZER0CODE"),
                ("Ctrl+B", "Toggle side panel"),
                ("Ctrl+L", "Clear conversation"),
                ("Ctrl+D", "Exit"),
                ("Ctrl+T", "Toggle theme"),
            ]
            for c, d in commands:
                help_text.append(f"\n  {c:<12}", style="bold cyan")
                help_text.append(d, style="dim")
            conv.write(help_text)

        elif command == "/clear":
            conv.clear()
            conv.write(Text("  Conversation cleared.", style="green"))
            if self.agent:
                self.agent.reset()

        elif command == "/tools":
            if self.agent:
                for name, tool in self.agent.tool_registry.items():
                    desc = getattr(tool, "description", "")[:50]
                    conv.write(Text(f"  {name:<20} {desc}", style="dim"))

        elif command == "/status":
            self._update_status()
            if self.agent:
                conv.write(Text(f"  Tokens: {self.agent.total_tokens:,} | Cost: {self.agent.total_cost} | Context: {self.agent.context_window_percent}%", style="cyan"))

        elif command == "/exit":
            self.exit()

        else:
            conv.write(Text(f"  Unknown command: {command}", style="yellow"))

    def action_toggle_panel(self) -> None:
        panel = self.query_one("#side-panel")
        conv = self.query_one("#conversation")
        self.show_panel = not self.show_panel
        if self.show_panel:
            panel.remove_class("hidden")
            conv.remove_class("full")
        else:
            panel.add_class("hidden")
            conv.add_class("full")

    def action_clear_log(self) -> None:
        conv = self.query_one("#conversation", ConversationLog)
        conv.clear()

    def action_toggle_theme(self) -> None:
        self.dark = not self.dark

    def _update_status(self):
        try:
            status = self.query_one("#status-bar", StatusBar)
            if self.config:
                status.provider = self.config.provider
                status.model = self.config.model
            if self.agent:
                status.tokens = self.agent.total_tokens
                status.cost = self.agent.total_cost
                status.context_pct = self.agent.context_window_percent
                status.session_id = self.agent.session_id or ""
        except Exception:
            pass


def run_tui(agent=None, config=None):
    if not HAS_TEXTUAL:
        print("Full-screen TUI requires 'textual'. Install with: pip install textual")
        print("Falling back to REPL mode.")
        return False
    app = ZeroCodeTUI(agent=agent, config=config)
    app.run()
    return True
