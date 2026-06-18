import asyncio
import json
import os
import time
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax
from rich.spinner import Spinner

HAS_TEXTUAL = False
try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Input, RichLog, Static
    from textual.reactive import reactive
    from textual.worker import Worker, get_current_worker
    HAS_TEXTUAL = True
except ImportError:
    pass


BANNER_LINES = [
    "  ░▒▓█████████████████████████████████████████████████▓▒░",
    "",
    "    █████ █████ ████   ███   ████  ███  ████  █████",
    "       █  █     █   █ █   █ █     █   █ █   █ █    ",
    "      █   ████  ████  █ ▀ █ █     █   █ █   █ ████ ",
    "     █    █     █  █  █   █ █     █   █ █   █ █    ",
    "    █████ █████ █   █  ███   ████  ███  ████  █████",
    "",
    "  ░▒▓█████████████████████████████████████████████████▓▒░",
]


if HAS_TEXTUAL:

    class ZeroStatusBar(Static):
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
            pct_style = "bold red" if self.context_pct > 80 else "yellow" if self.context_pct > 50 else "cyan"
            bar.append(f"ctx: {self.context_pct}%", style=pct_style)
            bar.append("  │  ", style="dim")
            bar.append(f"{self.session_id[:8]}", style="dim")
            cwd = os.getcwd()
            home = os.path.expanduser("~")
            if cwd.startswith(home):
                cwd = "~" + cwd[len(home):]
            bar.append("  │  ", style="dim")
            bar.append(cwd, style="dim")
            return bar

    class ZeroCodeTUI(App):
        TITLE = "ZER0CODE"

        CSS = """
        Screen {
            layout: vertical;
            background: $surface;
        }

        #header-bar {
            dock: top;
            height: 1;
            background: #111111;
            color: #00ff41;
            padding: 0 1;
        }

        #main-area {
            height: 1fr;
        }

        #conversation {
            width: 1fr;
            min-width: 40;
            scrollbar-size: 1 1;
        }

        #side-panel {
            width: 40;
            display: block;
            border-left: solid #333333;
            scrollbar-size: 1 1;
        }

        #side-panel.hidden {
            display: none;
        }

        #input-box {
            dock: bottom;
            height: 3;
            padding: 0 1;
            background: #0a0a0a;
        }

        #input-box Input {
            border: tall #00ff41;
            background: #111111;
            color: #00ff41;
        }

        #input-box Input:focus {
            border: tall #00ff88;
        }

        #status-bar {
            dock: bottom;
            height: 1;
            background: #111111;
        }

        RichLog {
            padding: 0 1;
            background: #0a0a0a;
            scrollbar-background: #111111;
            scrollbar-color: #333333;
        }
        """

        BINDINGS = [
            Binding("ctrl+b", "toggle_panel", "Panel", show=True),
            Binding("ctrl+l", "clear_conv", "Clear", show=True),
            Binding("ctrl+d", "quit", "Exit", show=True),
        ]

        show_panel = reactive(False)

        def __init__(self, agent=None, config=None, on_slash_command=None, **kwargs):
            super().__init__(**kwargs)
            self.agent = agent
            self.config = config
            self._on_slash_command = on_slash_command
            self._processing = False
            self._input_history: list[str] = []
            self._history_idx = -1

        def compose(self) -> ComposeResult:
            provider = self.config.provider if self.config else "?"
            model = self.config.model if self.config else "?"
            header_text = Text()
            header_text.append("  ⚡ ZER0CODE ", style="bold green")
            header_text.append("│ ", style="dim white")
            header_text.append(f"{provider}/{model} ", style="bold cyan")
            header_text.append("│ ", style="dim white")
            header_text.append("OPERATIONAL", style="bold green")
            yield Static(header_text, id="header-bar")

            with Horizontal(id="main-area"):
                yield RichLog(id="conversation", wrap=True, highlight=True, markup=True, max_lines=10000)
                yield RichLog(id="side-panel", wrap=True, highlight=True, markup=True, max_lines=5000, classes="hidden")

            with Vertical(id="input-box"):
                yield Input(placeholder="  Type a message or /help for commands...", id="user-input")

            yield ZeroStatusBar(id="status-bar")
            yield Footer()

        def on_mount(self) -> None:
            conv = self.query_one("#conversation", RichLog)

            for line in BANNER_LINES:
                conv.write(Text(line, style="bold green"))

            conv.write(Text(""))
            conv.write(Text("              ⚡ AUTONOMOUS PENTESTING AGENT ⚡", style="bold cyan"))
            conv.write(Text(""))

            info = Text()
            if self.config:
                info.append(f"  Provider: ", style="dim")
                info.append(f"{self.config.provider}", style="bold cyan")
                info.append(f"  │  Model: ", style="dim")
                info.append(f"{self.config.model}", style="bold cyan")
            if self.agent and self.agent.session_id:
                info.append(f"  │  Session: ", style="dim")
                info.append(f"{self.agent.session_id}", style="bold cyan")
            conv.write(info)

            tools_count = len(self.agent.tool_registry) if self.agent else 0
            conv.write(Text(f"  {tools_count} tools loaded  │  Type /help for commands  │  Ctrl+B toggle side panel\n", style="dim"))
            conv.write(Text("  ─" * 35, style="dim"))
            conv.write(Text(""))

            self._update_status()
            self.query_one("#user-input", Input).focus()

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id != "user-input":
                return

            user_input = event.value.strip()
            if not user_input:
                return

            inp = self.query_one("#user-input", Input)
            inp.value = ""

            self._input_history.append(user_input)
            self._history_idx = -1

            conv = self.query_one("#conversation", RichLog)

            if user_input.startswith("/"):
                await self._handle_slash(user_input, conv)
                return

            conv.write(Text(""))
            user_line = Text()
            user_line.append("  ❯ ", style="bold cyan")
            user_line.append(user_input, style="bold white")
            conv.write(user_line)
            conv.write(Text(""))

            if not self.agent:
                conv.write(Text("  Agent not initialized.", style="bold red"))
                return

            self._processing = True
            conv.write(Text("  ◐ Thinking...", style="dim yellow"))

            def on_tool_call(name, args):
                self.call_from_thread(self._show_tool_call, name, args)

            def on_tool_result(name, result, hook_msgs=None):
                self.call_from_thread(self._show_tool_result, name, result)

            self.agent.set_callbacks(on_tool_call=on_tool_call, on_tool_result=on_tool_result)

            self.run_worker(self._run_agent(user_input), thread=True)

        async def _run_agent(self, user_input: str) -> None:
            conv = self.query_one("#conversation", RichLog)
            try:
                response = await self.agent.run(user_input)
                if response:
                    try:
                        md = Markdown(response, code_theme="monokai")
                        conv.write(md)
                    except Exception:
                        conv.write(Text(f"  {response}", style="green"))

                    cost_line = Text()
                    cost_line.append("\n  ", style="")
                    cost_line.append(f"tokens: {self.agent.total_tokens:,}", style="dim cyan")
                    cost_line.append(f"  │  cost: {self.agent.total_cost}", style="dim cyan")
                    cost_line.append(f"  │  ctx: {self.agent.context_window_percent}%", style="dim cyan")
                    conv.write(cost_line)
            except Exception as e:
                error_panel = Panel(
                    Text(str(e), style="white"),
                    border_style="red",
                    title=Text("Error", style="bold red"),
                    title_align="left",
                    padding=(0, 1),
                )
                conv.write(error_panel)
            finally:
                self._processing = False
                self._update_status()

            conv.write(Text("  ─" * 35, style="dim"))
            conv.write(Text(""))

        def _show_tool_call(self, name: str, args: dict) -> None:
            conv = self.query_one("#conversation", RichLog)

            header = Text()
            header.append("  ▶ ", style="bold magenta")
            header.append(name, style="bold magenta")

            arg_text = Text()
            for k, v in args.items():
                val = str(v)
                if len(val) > 80:
                    val = val[:77] + "..."
                arg_text.append(f"    {k}", style="dim")
                arg_text.append("=", style="white")
                arg_text.append(f"{val}\n", style="cyan")

            from rich.console import Group
            panel = Panel(
                Group(header, arg_text),
                border_style="magenta",
                padding=(0, 1),
                expand=True,
            )
            conv.write(panel)

            side = self.query_one("#side-panel", RichLog)
            side.write(Text(f"\n  ▶ {name}", style="bold magenta"))
            for k, v in args.items():
                side.write(Text(f"    {k}={str(v)[:60]}", style="dim"))

        def _show_tool_result(self, name: str, result) -> None:
            conv = self.query_one("#conversation", RichLog)
            success = getattr(result, "success", True)
            output = getattr(result, "output", str(result)) if success else (getattr(result, "error", str(result)) or "Error")

            icon = "✓" if success else "✗"
            style = "green" if success else "red"

            header = Text()
            header.append(f"  {icon} ", style=f"bold {style}")
            header.append(name, style=f"bold {style}")

            display = output
            if len(display) > 1500:
                display = display[:750] + f"\n  ... ({len(output)} chars) ...\n" + display[-300:]

            result_text = Text(f"    {display}", style="dim")

            panel = Panel(
                result_text,
                border_style=style,
                title=header,
                title_align="left",
                padding=(0, 1),
                expand=True,
            )
            conv.write(panel)

            side = self.query_one("#side-panel", RichLog)
            side.write(Text(f"  {icon} {name}", style=style))
            side_output = output[:300] if len(output) > 300 else output
            side.write(Text(f"    {side_output}", style="dim"))

        async def _handle_slash(self, cmd: str, conv: RichLog) -> None:
            parts = cmd.strip().split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if command == "/help":
                help_cmds = [
                    ("/help", "Show this help"),
                    ("/clear", "Clear conversation"),
                    ("/tools", "List all tools"),
                    ("/status", "Show status"),
                    ("/config", "Show configuration"),
                    ("/model <name>", "Switch model"),
                    ("/provider <name>", "Switch provider"),
                    ("/skill", "List/load skills"),
                    ("/persona", "Switch agent persona"),
                    ("/template <name> <target>", "Run prompt template"),
                    ("/session list|load <id>", "Manage sessions"),
                    ("/export [file]", "Export to report"),
                    ("/compact", "Compact context"),
                    ("/cost", "Show cost breakdown"),
                    ("/budget <$>", "Set spending cap"),
                    ("/undo", "Rollback file changes"),
                    ("/branch", "Conversation branching"),
                    ("/doctor", "System health check"),
                    ("/init", "Generate .zer0code.md"),
                    ("/files", "Browse project files"),
                    ("/search <query>", "Search conversation"),
                    ("Ctrl+B", "Toggle side panel"),
                    ("Ctrl+L", "Clear conversation"),
                    ("Ctrl+D", "Exit"),
                ]
                conv.write(Text("\n  ZER0CODE Commands\n", style="bold green"))
                for c, d in help_cmds:
                    line = Text()
                    line.append(f"  {c:<28}", style="bold cyan")
                    line.append(d, style="dim")
                    conv.write(line)
                conv.write(Text(""))

            elif command == "/clear":
                conv.clear()
                if self.agent:
                    self.agent.reset()
                conv.write(Text("  Conversation cleared.\n", style="bold green"))

            elif command == "/tools":
                if self.agent:
                    conv.write(Text("\n  Registered Tools\n", style="bold magenta"))
                    for name, tool in sorted(self.agent.tool_registry.items()):
                        desc = getattr(tool, "description", "")[:50]
                        line = Text()
                        line.append(f"  {name:<22}", style="bold magenta")
                        line.append(desc, style="dim")
                        conv.write(line)
                    conv.write(Text(f"\n  {len(self.agent.tool_registry)} tools\n", style="dim"))

            elif command == "/status":
                self._update_status()
                if self.agent:
                    conv.write(Text(f"  Tokens: {self.agent.total_tokens:,} | Cost: {self.agent.total_cost} | Context: {self.agent.context_window_percent}% | Messages: {self.agent.message_count}", style="cyan"))

            elif command == "/config":
                if self.config:
                    conv.write(Text(f"  Provider: {self.config.provider}", style="cyan"))
                    conv.write(Text(f"  Model: {self.config.model}", style="cyan"))
                    conv.write(Text(f"  Theme: {self.config.theme}", style="cyan"))
                    conv.write(Text(f"  Memory: {self.config.memory_enabled}", style="cyan"))
                    conv.write(Text(f"  Session: {self.agent.session_id if self.agent else 'N/A'}", style="cyan"))

            elif command == "/exit" or command == "/quit":
                self.exit()

            elif command == "/model":
                if args and self.config:
                    self.config.model = args.strip()
                    self.config.save()
                    conv.write(Text(f"  Model switched to: {self.config.model}", style="bold green"))
                    self._update_status()
                else:
                    conv.write(Text(f"  Current model: {self.config.model if self.config else '?'}", style="dim"))

            elif command == "/provider":
                if args and self.config:
                    self.config.provider = args.strip()
                    self.config.save()
                    conv.write(Text(f"  Provider switched to: {self.config.provider}", style="bold green"))
                    self._update_status()
                else:
                    conv.write(Text(f"  Current: {self.config.provider if self.config else '?'} | Available: openai, anthropic, deepseek, ollama", style="dim"))

            elif command == "/cost":
                if self.agent:
                    s = self.agent.cost_tracker.summary()
                    conv.write(Text(f"  Tokens: {s['total_tokens']:,} (in: {s['input_tokens']:,}, out: {s['output_tokens']:,})", style="cyan"))
                    conv.write(Text(f"  Cost: {self.agent.total_cost} | Requests: {s['requests']}", style="cyan"))

            elif command == "/compact":
                if self.agent and self.agent.compactor:
                    old_len = len(self.agent.conversation_history)
                    self.agent.conversation_history = await self.agent.compactor.compact(self.agent.conversation_history)
                    new_len = len(self.agent.conversation_history)
                    conv.write(Text(f"  Compacted: {old_len} → {new_len} messages", style="bold green"))

            elif command == "/export":
                if self.agent:
                    filepath = args.strip() if args else f"zer0code-report-{int(time.time())}.md"
                    fmt = "html" if filepath.endswith(".html") else "md"
                    metadata = {"provider": self.config.provider if self.config else "", "model": self.config.model if self.config else "", "session_id": self.agent.session_id}
                    saved = self.agent.exporter.save(self.agent.conversation_history, filepath, format=fmt, metadata=metadata)
                    conv.write(Text(f"  Exported to: {saved}", style="bold green"))

            elif command == "/skill":
                from zer0code.skills.loader import SkillLoader
                loader = SkillLoader()
                if not args:
                    by_cat = loader.list_by_category()
                    for category, skills in by_cat.items():
                        conv.write(Text(f"\n  {category}", style="bold magenta"))
                        for skill in skills:
                            conv.write(Text(f"    {skill['name']:<22} {skill.get('description', '')[:45]}", style="dim"))
                    conv.write(Text(f"\n  {loader.count} skills | /skill <name> to load\n", style="dim"))
                else:
                    skill = loader.get_skill(args.strip())
                    if skill and self.agent:
                        self.agent.conversation_history.append({"role": "system", "content": f"LOADED SKILL: {skill.get('title', skill['name'])}\n\n{skill['system_prompt_addition']}"})
                        conv.write(Text(f"  Skill loaded: {skill.get('title', skill['name'])} ({skill.get('lines', '?')} lines)", style="bold green"))
                    else:
                        conv.write(Text(f"  Skill '{args.strip()}' not found.", style="red"))

            elif command == "/search":
                if self.agent and args:
                    query = args.strip().lower()
                    matches = 0
                    for i, m in enumerate(self.agent.conversation_history):
                        content = str(m.get("content", ""))
                        if query in content.lower():
                            role = m.get("role", "?")
                            snippet = content[:80].replace("\n", " ")
                            conv.write(Text(f"  [{i}] {role}: {snippet}", style="dim"))
                            matches += 1
                            if matches >= 15:
                                break
                    if matches == 0:
                        conv.write(Text(f"  No matches for '{args.strip()}'", style="dim"))

            elif command == "/files":
                if self.agent and self.agent.file_index:
                    if args:
                        results = self.agent.file_index.search(args.strip())
                        for r in results[:20]:
                            conv.write(Text(f"  {r}", style="dim"))
                    else:
                        tree = self.agent.file_index.get_tree()
                        conv.write(Text(tree, style="dim"))

            elif command == "/doctor":
                from zer0code.doctor import Doctor
                doc = Doctor()
                results = await doc.run_all()
                for check in results:
                    s = check["status"]
                    icon = "✓" if s == "pass" else "⚠" if s == "warn" else "✗"
                    style = "green" if s == "pass" else "yellow" if s == "warn" else "red"
                    conv.write(Text(f"  {icon} {check['name']:<18} {check['detail']}", style=style))
                conv.write(Text(f"\n  {doc.summary}\n", style="dim"))

            elif command == "/init":
                from zer0code.init_project import ProjectInitializer
                pi = ProjectInitializer()
                from pathlib import Path
                filepath = pi.save()
                conv.write(Text(f"  Generated: {filepath}", style="bold green"))

            elif command == "/persona":
                from zer0code.personas import PersonaManager
                pm = PersonaManager()
                if args and self.agent:
                    persona = pm.get_persona(args.strip())
                    if persona:
                        self.agent.conversation_history.append({"role": "system", "content": persona.system_prompt})
                        conv.write(Text(f"  Persona: {persona.title}", style="bold green"))
                    else:
                        conv.write(Text(f"  Available: {', '.join(pm.list_personas())}", style="dim"))
                else:
                    for name in pm.list_personas():
                        p = pm.get_persona(name)
                        conv.write(Text(f"  {name:<16} {p.title}", style="dim"))

            elif command == "/budget":
                if args and self.agent:
                    try:
                        self.agent.token_budget = float(args.strip().replace("$", ""))
                        conv.write(Text(f"  Budget set: ${self.agent.token_budget:.2f}", style="bold green"))
                    except ValueError:
                        conv.write(Text("  Usage: /budget <amount>", style="dim"))
                elif self.agent:
                    conv.write(Text(f"  Budget: ${self.agent.token_budget:.2f} | Spent: {self.agent.total_cost}", style="dim"))

            else:
                conv.write(Text(f"  Unknown command: {command}. Type /help", style="yellow"))

        def on_key(self, event) -> None:
            if event.key == "up" and not self._processing:
                if self._input_history:
                    if self._history_idx == -1:
                        self._history_idx = len(self._input_history) - 1
                    elif self._history_idx > 0:
                        self._history_idx -= 1
                    inp = self.query_one("#user-input", Input)
                    inp.value = self._input_history[self._history_idx]
                    inp.cursor_position = len(inp.value)
            elif event.key == "down" and not self._processing:
                if self._history_idx >= 0:
                    self._history_idx += 1
                    inp = self.query_one("#user-input", Input)
                    if self._history_idx >= len(self._input_history):
                        self._history_idx = -1
                        inp.value = ""
                    else:
                        inp.value = self._input_history[self._history_idx]
                        inp.cursor_position = len(inp.value)

        def action_toggle_panel(self) -> None:
            panel = self.query_one("#side-panel")
            self.show_panel = not self.show_panel
            if self.show_panel:
                panel.remove_class("hidden")
            else:
                panel.add_class("hidden")

        def action_clear_conv(self) -> None:
            conv = self.query_one("#conversation", RichLog)
            conv.clear()
            if self.agent:
                self.agent.reset()

        def _update_status(self) -> None:
            try:
                status = self.query_one("#status-bar", ZeroStatusBar)
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
        print("\n  ZER0CODE TUI requires 'textual'.")
        print("  Install: pip install 'zer0code[tui]' or pip install textual")
        print("  Falling back to REPL mode.\n")
        return False
    app = ZeroCodeTUI(agent=agent, config=config)
    app.run()
    return True
