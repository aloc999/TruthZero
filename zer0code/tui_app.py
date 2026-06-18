import asyncio
import os
import time
from datetime import datetime
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax

HAS_TEXTUAL = False
try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Input, RichLog, Static
    from textual.reactive import reactive
    from textual.suggester import SuggestFromList
    from textual.timer import Timer
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

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

SLASH_COMMANDS = [
    "/help", "/clear", "/tools", "/status", "/config", "/model", "/provider",
    "/skill", "/persona", "/template", "/session", "/compact", "/cost",
    "/budget", "/export", "/undo", "/branch", "/doctor", "/init", "/files",
    "/search", "/theme", "/step", "/exit", "/quit",
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

    class ContextBreadcrumb(Static):
        persona_name = reactive("default")
        loaded_skills = reactive("")
        branch_name = reactive("main")

        def render(self) -> Text:
            bc = Text()
            bc.append("  ", style="")
            if self.persona_name != "default":
                bc.append(f"⚔ {self.persona_name}", style="bold magenta")
                bc.append("  ", style="")
            if self.loaded_skills:
                bc.append(f"📚 {self.loaded_skills}", style="bold cyan")
                bc.append("  ", style="")
            if self.branch_name != "main":
                bc.append(f"⑂ {self.branch_name}", style="bold yellow")
            return bc

    class SpinnerWidget(Static):
        frame_idx = reactive(0)
        action = reactive("")
        elapsed = reactive(0.0)
        active = reactive(False)

        def render(self) -> Text:
            if not self.active:
                return Text("")
            spinner = SPINNER_FRAMES[self.frame_idx % len(SPINNER_FRAMES)]
            t = Text()
            t.append(f"  {spinner} ", style="bold green")
            t.append(self.action or "Thinking", style="bold yellow")
            if self.elapsed > 0:
                t.append(f"  ({self.elapsed:.1f}s)", style="dim")
            return t

    class ZeroCodeTUI(App):
        TITLE = "ZER0CODE"

        CSS = """
        Screen {
            layout: vertical;
            background: #0a0a0a;
        }

        #header-bar {
            dock: top;
            height: 1;
            background: #111111;
            color: #00ff41;
            padding: 0 1;
        }

        #breadcrumb {
            dock: top;
            height: 1;
            background: #0d0d0d;
        }

        #spinner-bar {
            dock: bottom;
            height: 1;
            background: #0d0d0d;
        }

        #main-area {
            height: 1fr;
        }

        #conversation {
            width: 1fr;
            min-width: 40;
            scrollbar-size: 1 1;
            background: #0a0a0a;
            scrollbar-background: #111111;
            scrollbar-color: #333333;
        }

        #side-panel {
            width: 45;
            display: none;
            border-left: solid #333333;
            background: #0a0a0a;
            scrollbar-size: 1 1;
            scrollbar-background: #111111;
            scrollbar-color: #333333;
        }

        #side-panel.visible {
            display: block;
        }

        #input-box {
            dock: bottom;
            height: auto;
            max-height: 6;
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
        }

        Footer {
            background: #111111;
        }
        """

        BINDINGS = [
            Binding("ctrl+b", "toggle_panel", "Panel", show=True),
            Binding("ctrl+l", "clear_conv", "Clear", show=True),
            Binding("ctrl+d", "app_exit", "Exit", show=True),
            Binding("ctrl+t", "toggle_dark", "Theme", show=True),
            Binding("ctrl+f", "search_conv", "Search", show=True),
            Binding("ctrl+s", "toggle_scroll", "Scroll", show=False),
        ]

        show_panel = reactive(False)
        auto_scroll = reactive(True)
        step_mode = reactive(False)

        def __init__(self, agent=None, config=None, **kwargs):
            super().__init__(**kwargs)
            self.agent = agent
            self.config = config
            self._processing = False
            self._input_history: list[str] = []
            self._history_idx = -1
            self._spinner_timer: Optional[Timer] = None
            self._tool_start_time = 0.0
            self._process_start_time = 0.0
            self._search_mode = False

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
            yield ContextBreadcrumb(id="breadcrumb")

            with Horizontal(id="main-area"):
                yield RichLog(id="conversation", wrap=True, highlight=True, markup=True, max_lines=50000, auto_scroll=True)
                yield RichLog(id="side-panel", wrap=True, highlight=True, markup=True, max_lines=10000)

            yield SpinnerWidget(id="spinner-bar")

            with Vertical(id="input-box"):
                yield Input(
                    placeholder="  Message or /command...",
                    id="user-input",
                    suggester=SuggestFromList(SLASH_COMMANDS, case_sensitive=False),
                )

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
            conv.write(Text(f"  {tools_count} tools  │  /help for commands  │  Ctrl+B side panel  │  Ctrl+F search", style="dim"))
            conv.write(Text(""))
            conv.write(Text("  ─" * 35, style="dim"))
            conv.write(Text(""))

            self._update_status()
            self.query_one("#user-input", Input).focus()

        def _start_spinner(self, action: str = "Thinking") -> None:
            spinner = self.query_one("#spinner-bar", SpinnerWidget)
            spinner.active = True
            spinner.action = action
            spinner.elapsed = 0.0
            self._process_start_time = time.monotonic()
            if self._spinner_timer:
                self._spinner_timer.stop()
            self._spinner_timer = self.set_interval(0.1, self._tick_spinner)

        def _tick_spinner(self) -> None:
            try:
                spinner = self.query_one("#spinner-bar", SpinnerWidget)
                spinner.frame_idx += 1
                spinner.elapsed = time.monotonic() - self._process_start_time
            except Exception:
                pass

        def _stop_spinner(self) -> None:
            if self._spinner_timer:
                self._spinner_timer.stop()
                self._spinner_timer = None
            try:
                spinner = self.query_one("#spinner-bar", SpinnerWidget)
                spinner.active = False
            except Exception:
                pass

        def _update_spinner_action(self, action: str) -> None:
            try:
                spinner = self.query_one("#spinner-bar", SpinnerWidget)
                spinner.action = action
            except Exception:
                pass

        def _ts(self) -> str:
            return datetime.now().strftime("%H:%M:%S")

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id != "user-input":
                return
            user_input = event.value.strip()
            if not user_input:
                return

            inp = self.query_one("#user-input", Input)
            inp.value = ""

            if self._search_mode:
                self._do_search(user_input)
                self._search_mode = False
                inp.placeholder = "  Message or /command..."
                return

            self._input_history.append(user_input)
            self._history_idx = -1

            conv = self.query_one("#conversation", RichLog)

            if user_input.startswith("/"):
                await self._handle_slash(user_input, conv)
                return

            ts = self._ts()
            conv.write(Text(""))
            user_line = Text()
            user_line.append(f"  {ts} ", style="dim")
            user_line.append("❯ ", style="bold cyan")
            user_line.append(user_input, style="bold white")
            conv.write(user_line)
            conv.write(Text(""))

            if not self.agent:
                conv.write(Panel(Text("Agent not initialized", style="white"), border_style="red", title="Error"))
                return

            self._processing = True
            self._start_spinner("Thinking")

            def on_tool_call(name, args):
                self.call_from_thread(self._update_spinner_action, f"Running {name}")
                self.call_from_thread(self._show_tool_call, name, args)

            def on_tool_result(name, result, hook_msgs=None):
                self.call_from_thread(self._show_tool_result, name, result)

            self.agent.set_callbacks(on_tool_call=on_tool_call, on_tool_result=on_tool_result)
            self.run_worker(self._run_agent_stream(user_input), thread=True)

        async def _run_agent_stream(self, user_input: str) -> None:
            conv = self.query_one("#conversation", RichLog)
            ts = self._ts()
            collected_text = []

            try:
                async for chunk in self.agent.run_stream(user_input):
                    if isinstance(chunk, str):
                        collected_text.append(chunk)
                        partial = "".join(collected_text)
                        if len(partial) % 20 == 0 or chunk.endswith("\n"):
                            self.call_from_thread(self._update_spinner_action, "Generating")
                    elif isinstance(chunk, dict):
                        chunk_type = chunk.get("type", "")
                        if chunk_type == "tool_call":
                            self.call_from_thread(self._update_spinner_action, f"Running {chunk.get('name', '?')}")
                        elif chunk_type == "tool_result":
                            pass

                full_response = "".join(collected_text)
                if full_response:
                    thinking_text, response_text = self._extract_thinking(full_response)

                    if thinking_text:
                        think_panel = Panel(
                            Text(thinking_text[:2000], style="dim italic"),
                            border_style="dim",
                            title=Text("Thinking", style="dim italic"),
                            title_align="left",
                            padding=(0, 1),
                        )
                        conv.write(think_panel)

                    try:
                        md = Markdown(response_text, code_theme="monokai")
                        conv.write(md)
                    except Exception:
                        conv.write(Text(f"  {response_text}", style="green"))

                    cost_line = Text()
                    cost_line.append(f"\n  {self._ts()} ", style="dim")
                    cost_line.append(f"tokens: {self.agent.total_tokens:,}", style="dim cyan")
                    cost_line.append(f"  │  cost: {self.agent.total_cost}", style="dim cyan")
                    cost_line.append(f"  │  ctx: {self.agent.context_window_percent}%", style="dim cyan")
                    elapsed = time.monotonic() - self._process_start_time
                    cost_line.append(f"  │  {elapsed:.1f}s", style="dim")
                    conv.write(cost_line)

            except Exception as e:
                conv.write(Panel(Text(str(e), style="white"), border_style="red", title=Text("Error", style="bold red"), padding=(0, 1)))
            finally:
                self._processing = False
                self._stop_spinner()
                self._update_status()
                conv.write(Text(""))
                conv.write(Text("  ─" * 35, style="dim"))
                conv.write(Text(""))

                if elapsed > 10:
                    try:
                        from zer0code.notifications import NotificationManager
                        nm = NotificationManager()
                        nm.task_complete("Response ready", elapsed)
                    except Exception:
                        pass

        def _extract_thinking(self, text: str) -> tuple[str, str]:
            import re
            think_match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
            if think_match:
                thinking = think_match.group(1).strip()
                response = text[:think_match.start()] + text[think_match.end():]
                return thinking, response.strip()
            think_match = re.search(r"<thinking>(.*?)</thinking>", text, re.DOTALL)
            if think_match:
                thinking = think_match.group(1).strip()
                response = text[:think_match.start()] + text[think_match.end():]
                return thinking, response.strip()
            return "", text

        def _show_tool_call(self, name: str, args: dict) -> None:
            conv = self.query_one("#conversation", RichLog)
            ts = self._ts()

            header = Text()
            header.append(f"  {ts} ", style="dim")
            header.append("▶ ", style="bold magenta")
            header.append(name, style="bold magenta")
            self._tool_start_time = time.monotonic()

            arg_text = Text()
            for k, v in args.items():
                val = str(v)
                if len(val) > 100:
                    val = val[:97] + "..."
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
            side.write(Text(f"\n  {ts}  ▶ {name}", style="bold magenta"))
            for k, v in args.items():
                side.write(Text(f"    {k}={str(v)[:60]}", style="dim"))

        def _show_tool_result(self, name: str, result) -> None:
            conv = self.query_one("#conversation", RichLog)
            ts = self._ts()
            tool_elapsed = time.monotonic() - self._tool_start_time
            success = getattr(result, "success", True)
            output = getattr(result, "output", str(result)) if success else (getattr(result, "error", str(result)) or "Error")

            icon = "✓" if success else "✗"
            style = "green" if success else "red"

            title = Text()
            title.append(f" {icon} ", style=f"bold {style}")
            title.append(name, style=f"bold {style}")
            title.append(f"  ({tool_elapsed:.1f}s)", style="dim")

            display = output
            if len(display) > 2000:
                display = display[:1000] + f"\n  ... ({len(output)} chars total) ...\n" + display[-500:]

            if name == "edit_file" and success:
                self._show_diff_result(conv, display, name, title)
            else:
                result_text = Text(display, style="dim")
                panel = Panel(result_text, border_style=style, title=title, title_align="left", padding=(0, 1), expand=True)
                conv.write(panel)

            side = self.query_one("#side-panel", RichLog)
            side.write(Text(f"  {ts}  {icon} {name} ({tool_elapsed:.1f}s)", style=style))
            side_out = output[:200] if len(output) > 200 else output
            side.write(Text(f"    {side_out}", style="dim"))

        def _show_diff_result(self, conv: RichLog, output: str, name: str, title: Text) -> None:
            diff_text = Text()
            for line in output.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    diff_text.append(line + "\n", style="green")
                elif line.startswith("-") and not line.startswith("---"):
                    diff_text.append(line + "\n", style="red")
                elif line.startswith("@@"):
                    diff_text.append(line + "\n", style="cyan")
                else:
                    diff_text.append(line + "\n", style="dim")
            panel = Panel(diff_text, border_style="cyan", title=title, title_align="left", padding=(0, 1), expand=True)
            conv.write(panel)

        def _do_search(self, query: str) -> None:
            conv = self.query_one("#conversation", RichLog)
            if not self.agent:
                return
            query_lower = query.lower()
            matches = 0
            for i, m in enumerate(self.agent.conversation_history):
                content = str(m.get("content", ""))
                if query_lower in content.lower():
                    role = m.get("role", "?")
                    snippet = content[:100].replace("\n", " ")
                    conv.write(Text(f"  [{i}] {role}: {snippet}", style="dim"))
                    matches += 1
                    if matches >= 15:
                        break
            if matches == 0:
                conv.write(Text(f"  No matches for '{query}'", style="dim yellow"))
            else:
                conv.write(Text(f"  {matches} match(es) found", style="dim green"))

        async def _handle_slash(self, cmd: str, conv: RichLog) -> None:
            parts = cmd.strip().split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            if command == "/help":
                help_cmds = [
                    ("/help", "Show commands"),
                    ("/clear", "Clear conversation"),
                    ("/tools", "List all tools"),
                    ("/status", "Show status"),
                    ("/config", "Show configuration"),
                    ("/model <name>", "Switch model"),
                    ("/provider <name>", "Switch provider"),
                    ("/skill [name]", "List/load skills"),
                    ("/persona [name]", "Switch persona"),
                    ("/template <n> <t>", "Run template"),
                    ("/session list|load", "Sessions"),
                    ("/export [file]", "Export report"),
                    ("/compact", "Compact context"),
                    ("/cost", "Cost breakdown"),
                    ("/budget <$>", "Spending cap"),
                    ("/undo [all]", "Rollback changes"),
                    ("/branch", "Branching"),
                    ("/doctor", "Health check"),
                    ("/init", "Generate .zer0code.md"),
                    ("/files [query]", "Project files"),
                    ("/search <query>", "Search history"),
                    ("/step", "Toggle step mode"),
                    ("/theme", "Toggle theme"),
                    ("Ctrl+B", "Toggle side panel"),
                    ("Ctrl+F", "Search conversation"),
                    ("Ctrl+L", "Clear"),
                    ("Ctrl+T", "Toggle theme"),
                    ("Ctrl+D", "Exit"),
                    ("Up/Down", "Input history"),
                ]
                conv.write(Text("\n  ZER0CODE Commands\n", style="bold green"))
                for c, d in help_cmds:
                    line = Text()
                    line.append(f"  {c:<22}", style="bold cyan")
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
                    for k, v in [("Provider", self.config.provider), ("Model", self.config.model), ("Theme", self.config.theme), ("Memory", str(self.config.memory_enabled)), ("Session", self.agent.session_id if self.agent else "N/A")]:
                        conv.write(Text(f"  {k}: {v}", style="cyan"))

            elif command == "/model":
                if args and self.config:
                    self.config.model = args.strip()
                    self.config.save()
                    conv.write(Text(f"  Model → {self.config.model}", style="bold green"))
                    self._update_status()
                    self._update_header()
                else:
                    conv.write(Text(f"  Current: {self.config.model if self.config else '?'}", style="dim"))

            elif command == "/provider":
                if args and self.config:
                    p = args.strip().lower()
                    if p in ("openai", "anthropic", "deepseek", "ollama"):
                        self.config.provider = p
                        self.config.save()
                        conv.write(Text(f"  Provider → {p}", style="bold green"))
                        self._update_status()
                        self._update_header()
                    else:
                        conv.write(Text("  Valid: openai, anthropic, deepseek, ollama", style="red"))
                else:
                    conv.write(Text(f"  Current: {self.config.provider if self.config else '?'}", style="dim"))

            elif command == "/cost":
                if self.agent:
                    s = self.agent.cost_tracker.summary()
                    conv.write(Text(f"  Total: {s['total_tokens']:,} tokens (in: {s['input_tokens']:,}, out: {s['output_tokens']:,})", style="cyan"))
                    conv.write(Text(f"  Cost: {self.agent.total_cost} | Requests: {s['requests']}", style="cyan"))

            elif command == "/compact":
                if self.agent and self.agent.compactor:
                    old = len(self.agent.conversation_history)
                    self.agent.conversation_history = await self.agent.compactor.compact(self.agent.conversation_history)
                    conv.write(Text(f"  Compacted: {old} → {len(self.agent.conversation_history)} messages", style="bold green"))

            elif command == "/export":
                if self.agent:
                    filepath = args.strip() if args else f"zer0code-report-{int(time.time())}.md"
                    fmt = "html" if filepath.endswith(".html") else "md"
                    metadata = {"provider": self.config.provider if self.config else "", "model": self.config.model if self.config else "", "session_id": self.agent.session_id}
                    saved = self.agent.exporter.save(self.agent.conversation_history, filepath, format=fmt, metadata=metadata)
                    conv.write(Text(f"  Exported → {saved}", style="bold green"))

            elif command == "/skill":
                from zer0code.skills.loader import SkillLoader
                loader = SkillLoader()
                if not args:
                    for cat, skills in loader.list_by_category().items():
                        conv.write(Text(f"\n  {cat}", style="bold magenta"))
                        for sk in skills:
                            conv.write(Text(f"    {sk['name']:<22} {sk.get('description', '')[:40]}", style="dim"))
                    conv.write(Text(f"\n  {loader.count} skills | /skill <name> to load\n", style="dim"))
                else:
                    skill = loader.get_skill(args.strip())
                    if skill and self.agent:
                        self.agent.conversation_history.append({"role": "system", "content": f"LOADED SKILL: {skill.get('title', skill['name'])}\n\n{skill['system_prompt_addition']}"})
                        conv.write(Text(f"  Loaded: {skill.get('title', skill['name'])} ({skill.get('lines', '?')} lines)", style="bold green"))
                        self._update_breadcrumb(skill_name=args.strip())
                    else:
                        conv.write(Text(f"  Not found: {args.strip()}", style="red"))

            elif command == "/persona":
                from zer0code.personas import PersonaManager
                pm = PersonaManager()
                if args and self.agent:
                    persona = pm.get_persona(args.strip())
                    if persona:
                        self.agent.conversation_history.append({"role": "system", "content": persona.system_prompt})
                        conv.write(Text(f"  Persona → {persona.title}", style="bold green"))
                        self._update_breadcrumb(persona_name=args.strip())
                    else:
                        conv.write(Text(f"  Available: {', '.join(pm.list_personas())}", style="dim"))
                else:
                    for name in pm.list_personas():
                        p = pm.get_persona(name)
                        conv.write(Text(f"  {name:<16} {p.title}", style="dim"))

            elif command == "/search":
                if args:
                    self._do_search(args.strip())
                else:
                    conv.write(Text("  Usage: /search <query>", style="dim"))

            elif command == "/doctor":
                from zer0code.doctor import Doctor
                doc = Doctor()
                results = await doc.run_all()
                for check in results:
                    s = check["status"]
                    icon = "✓" if s == "pass" else "⚠" if s == "warn" else "✗"
                    st = "green" if s == "pass" else "yellow" if s == "warn" else "red"
                    conv.write(Text(f"  {icon} {check['name']:<18} {check['detail']}", style=st))
                conv.write(Text(f"\n  {doc.summary}\n", style="dim"))

            elif command == "/init":
                from zer0code.init_project import ProjectInitializer
                from pathlib import Path
                pi = ProjectInitializer()
                fp = pi.save()
                conv.write(Text(f"  Generated → {fp}", style="bold green"))

            elif command == "/files":
                if self.agent and self.agent.file_index:
                    if args:
                        for r in self.agent.file_index.search(args.strip())[:20]:
                            conv.write(Text(f"  {r}", style="dim"))
                    else:
                        conv.write(Text(self.agent.file_index.get_tree(), style="dim"))

            elif command == "/step":
                self.step_mode = not self.step_mode
                conv.write(Text(f"  Step mode: {'ON' if self.step_mode else 'OFF'}", style="bold green"))

            elif command == "/theme":
                self.dark = not self.dark
                conv.write(Text(f"  Theme toggled", style="bold green"))

            elif command == "/budget":
                if args and self.agent:
                    try:
                        self.agent.token_budget = float(args.strip().replace("$", ""))
                        conv.write(Text(f"  Budget → ${self.agent.token_budget:.2f}", style="bold green"))
                    except ValueError:
                        conv.write(Text("  Usage: /budget <amount>", style="dim"))
                elif self.agent:
                    conv.write(Text(f"  Budget: ${self.agent.token_budget:.2f} | Spent: {self.agent.total_cost}", style="dim"))

            elif command == "/undo":
                if self.agent:
                    if args == "all":
                        restored = self.agent.rollback.rollback_all()
                        conv.write(Text(f"  Restored {len(restored)} files", style="bold green"))
                    elif args == "list":
                        for c in self.agent.rollback.list_changes():
                            conv.write(Text(f"  {c['filepath']}", style="dim"))
                    elif args:
                        if self.agent.rollback.rollback(args.strip()):
                            conv.write(Text(f"  Restored: {args.strip()}", style="bold green"))
                        else:
                            conv.write(Text(f"  No snapshot for: {args.strip()}", style="red"))
                    else:
                        conv.write(Text("  Usage: /undo [all|list|<file>]", style="dim"))

            elif command == "/branch":
                if self.agent:
                    if not args or args == "list":
                        for b in self.agent.brancher.list_branches():
                            marker = " ◀" if b["current"] else ""
                            conv.write(Text(f"  {b['name']:<16} {b['messages']} msgs{marker}", style="dim"))
                    elif args.startswith("create "):
                        name = self.agent.brancher.create_branch(args[7:].strip())
                        self.agent.brancher.switch_branch(name)
                        self.agent.conversation_history = self.agent.brancher.current_messages
                        conv.write(Text(f"  Branch created → {name}", style="bold green"))
                        self._update_breadcrumb(branch_name=name)
                    elif args.startswith("switch "):
                        if self.agent.brancher.switch_branch(args[7:].strip()):
                            self.agent.conversation_history = self.agent.brancher.current_messages
                            conv.write(Text(f"  Switched → {args[7:].strip()}", style="bold green"))
                            self._update_breadcrumb(branch_name=args[7:].strip())

            elif command in ("/exit", "/quit"):
                self.exit()

            else:
                conv.write(Text(f"  Unknown: {command}  — type /help", style="yellow"))

        def on_key(self, event) -> None:
            if self._processing:
                return
            if event.key == "up":
                if self._input_history:
                    if self._history_idx == -1:
                        self._history_idx = len(self._input_history) - 1
                    elif self._history_idx > 0:
                        self._history_idx -= 1
                    try:
                        inp = self.query_one("#user-input", Input)
                        inp.value = self._input_history[self._history_idx]
                        inp.cursor_position = len(inp.value)
                    except Exception:
                        pass
            elif event.key == "down":
                if self._history_idx >= 0:
                    self._history_idx += 1
                    try:
                        inp = self.query_one("#user-input", Input)
                        if self._history_idx >= len(self._input_history):
                            self._history_idx = -1
                            inp.value = ""
                        else:
                            inp.value = self._input_history[self._history_idx]
                            inp.cursor_position = len(inp.value)
                    except Exception:
                        pass

        def action_toggle_panel(self) -> None:
            panel = self.query_one("#side-panel")
            self.show_panel = not self.show_panel
            if self.show_panel:
                panel.add_class("visible")
            else:
                panel.remove_class("visible")

        def action_clear_conv(self) -> None:
            conv = self.query_one("#conversation", RichLog)
            conv.clear()
            if self.agent:
                self.agent.reset()

        def action_app_exit(self) -> None:
            self.exit()

        def action_toggle_dark(self) -> None:
            self.dark = not self.dark

        def action_search_conv(self) -> None:
            self._search_mode = True
            inp = self.query_one("#user-input", Input)
            inp.placeholder = "  🔍 Search conversation (Enter to search, type query)..."
            inp.focus()

        def action_toggle_scroll(self) -> None:
            self.auto_scroll = not self.auto_scroll
            conv = self.query_one("#conversation", RichLog)
            conv.auto_scroll = self.auto_scroll

        def _update_header(self) -> None:
            try:
                header = self.query_one("#header-bar", Static)
                ht = Text()
                ht.append("  ⚡ ZER0CODE ", style="bold green")
                ht.append("│ ", style="dim white")
                if self.config:
                    ht.append(f"{self.config.provider}/{self.config.model} ", style="bold cyan")
                ht.append("│ ", style="dim white")
                ht.append("OPERATIONAL", style="bold green")
                header.update(ht)
            except Exception:
                pass

        def _update_breadcrumb(self, persona_name: str = None, skill_name: str = None, branch_name: str = None) -> None:
            try:
                bc = self.query_one("#breadcrumb", ContextBreadcrumb)
                if persona_name is not None:
                    bc.persona_name = persona_name
                if skill_name is not None:
                    current = bc.loaded_skills
                    if current:
                        bc.loaded_skills = f"{current}, {skill_name}"
                    else:
                        bc.loaded_skills = skill_name
                if branch_name is not None:
                    bc.branch_name = branch_name
            except Exception:
                pass

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
