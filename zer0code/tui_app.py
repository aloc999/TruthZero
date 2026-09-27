import asyncio
import os
import time
from datetime import datetime
from typing import Optional

from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.console import Group
from rich import box

HAS_TEXTUAL = False
try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Input, RichLog, Static, OptionList, Button
    from textual.widgets.option_list import Option
    from textual.screen import ModalScreen
    from textual.reactive import reactive
    from textual.suggester import SuggestFromList
    from textual.timer import Timer
    HAS_TEXTUAL = True
except ImportError:
    pass

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

SLASH_COMMANDS = [
    "/help", "/clear", "/tools", "/status", "/config", "/model", "/provider",
    "/skill", "/persona", "/template", "/session", "/compact", "/cost",
    "/budget", "/export", "/undo", "/branch", "/doctor", "/init", "/files",
    "/search", "/theme", "/step", "/exit", "/quit", "/copy",
    "/scan", "/lab", "/bench",
]

# -- neon palettes: config theme -> TUI colors (cyberpunk default energy) --
TUI_PALETTES = {
    "hacker": {"primary": "#00ff41", "accent": "#00d0ff", "hot": "#00ff88",
               "warn": "#ffff00", "err": "#ff3131", "persona": "#ff00ff",
               "bg": "#0a0a0a", "surface": "#111111", "edge": "#333333"},
    "cyberpunk": {"primary": "#ff2a6d", "accent": "#00f0ff", "hot": "#05ffa1",
                  "warn": "#ffd319", "err": "#ff3131", "persona": "#7b2ff7",
                  "bg": "#05010f", "surface": "#0d0221", "edge": "#7b2ff7"},
    "dark": {"primary": "#4d9fff", "accent": "#00d0ff", "hot": "#00ffa1",
             "warn": "#ffb000", "err": "#ff5555", "persona": "#bb88ff",
             "bg": "#0d1117", "surface": "#161b22", "edge": "#30363d"},
    "minimal": {"primary": "#ffffff", "accent": "#00e5ff", "hot": "#ffffff",
                "warn": "#ffff00", "err": "#ff5555", "persona": "#ffffff",
                "bg": "#000000", "surface": "#0a0a0a", "edge": "#444444"},
}


def tui_palette(theme_name: str | None) -> dict:
    return TUI_PALETTES.get(theme_name or "hacker", TUI_PALETTES["hacker"])


def _app_pal(widget) -> dict:
    try:
        return widget.app._tui_pal
    except Exception:
        return TUI_PALETTES["hacker"]

def build_tui_css(template: str, pal: dict) -> str:
    """Render the Textual stylesheet for a palette (safe substitute)."""
    import string
    return string.Template(template).safe_substitute(pal)

def _st(pal: dict, role: str, bold: True | bool = True, pre: str = "") -> str:
    return f"{pre}{'bold ' if bold else ''}{pal[role]}"


_SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 24) -> str:
    vals = [float(v) for v in list(values)[-width:]] or [0.0]
    mx = max(vals) or 1.0
    return "".join(_SPARK[min(int(v / mx * 7), 7)] for v in vals)


def meter(frac: float, width: int = 20) -> str:
    f = max(0.0, min(1.0, float(frac)))
    n = int(round(f * width))
    return "█" * n + "░" * (width - n)


def risk_of_severity(counts: dict) -> tuple[int, str]:
    c = counts.get("critical", 0)
    h = counts.get("high", 0)
    med = counts.get("medium", 0)
    low = counts.get("low", 0)
    if c > 0:
        base, band = 85, "CRITICAL"
    elif h > 0:
        base, band = 65, "HIGH"
    elif med > 0:
        base, band = 42, "MEDIUM"
    elif low > 0:
        base, band = 18, "LOW"
    else:
        return 0, "NONE"
    return min(100, base + min(15, (c + h + med + low) * 3)), band

if HAS_TEXTUAL:

    class ZeroStatusBar(Static):
        tokens = reactive(0)
        cost = reactive("$0.00")
        context_pct = reactive(0)
        session_id = reactive("")
        model = reactive("")
        provider = reactive("")

        def render(self) -> Text:
            pal = _app_pal(self)
            bar = Text()
            bar.append(" ⚡ ", style=_st(pal, "warn"))
            bar.append(f"{self.provider}", style=_st(pal, "primary"))
            bar.append("/", style="dim")
            bar.append(f"{self.model}", style=_st(pal, "primary"))
            bar.append("  │  ", style="dim")
            bar.append(f"tokens: {self.tokens:,}", style=_st(pal, "accent", bold=False))
            bar.append("  │  ", style="dim")
            bar.append(f"{self.cost}", style=_st(pal, "accent", bold=False))
            bar.append("  │  ", style="dim")
            pct_style = _st(pal, "err") if self.context_pct > 80 else _st(pal, "warn", bold=False) if self.context_pct > 50 else _st(pal, "accent", bold=False)
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
            pal = _app_pal(self)
            bc = Text()
            bc.append("  ", style="")
            if self.persona_name != "default":
                bc.append(f"⚔ {self.persona_name}", style=_st(pal, "persona"))
                bc.append("  ", style="")
            if self.loaded_skills:
                bc.append(f"📚 {self.loaded_skills}", style=_st(pal, "accent"))
                bc.append("  ", style="")
            if self.branch_name != "main":
                bc.append(f"⑂ {self.branch_name}", style=_st(pal, "warn"))
            return bc

    class SpinnerWidget(Static):
        frame_idx = reactive(0)
        action = reactive("")
        elapsed = reactive(0.0)
        active = reactive(False)

        def render(self) -> Text:
            pal = _app_pal(self)
            if not self.active:
                return Text("")
            spinner = SPINNER_FRAMES[self.frame_idx % len(SPINNER_FRAMES)]
            t = Text()
            t.append(f"  {spinner} ", style=_st(pal, "primary"))
            t.append(self.action or "Thinking", style=_st(pal, "warn"))
            if self.elapsed > 0:
                t.append(f"  ({self.elapsed:.1f}s)", style="dim")
            return t

    class PickerScreen(ModalScreen):
        """Opencode-style picker: ↑/↓ + enter to pick, esc cancels."""

        BINDINGS = [
            Binding("escape", "dismiss_picker", "Cancel", show=False),
        ]

        def __init__(self, title: str, options: list[str]):
            super().__init__()
            self._title = title
            self._options = options

        def compose(self) -> ComposeResult:
            yield Static(f"  ◢ {self._title}  (esc cancels)", id="picker-title")
            yield OptionList(
                *[Option(o, id=f"opt-{i}") for i, o in enumerate(self._options)],
                id="picker-list",
            )

        def on_mount(self) -> None:
            self.query_one("#picker-list", OptionList).focus()

        def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
            idx = int(event.option.id.split("-")[1])
            self.dismiss(self._options[idx])

        def action_dismiss_picker(self) -> None:
            self.dismiss(None)

    class ZeroCodeTUI(App):
        TITLE = "ZER0CODE"

        _CSS_TEMPLATE = """
        Screen {
            layout: vertical;
            background: $bg;
        }

        #header-bar {
            dock: top;
            height: 1;
            background: $surface;
            color: $primary;
            padding: 0 1;
        }

        #breadcrumb {
            dock: top;
            height: 1;
            background: $surface;
        }

        #spinner-bar {
            dock: bottom;
            height: 1;
            display: none;
            background: $surface;
        }

        #main-area {
            height: 1fr;
        }

        #conversation {
            width: 1fr;
            min-width: 40;
            scrollbar-size: 1 1;
            background: $bg;
            scrollbar-background: $surface;
            scrollbar-color: $edge;
        }

        #side-panel {
            width: 45;
            display: none;
            border-left: solid $edge;
            background: $bg;
            scrollbar-size: 1 1;
            scrollbar-background: $surface;
            scrollbar-color: $edge;
        }

        #side-panel.visible {
            display: block;
        }

        #input-box {
            dock: bottom;
            height: 3;
            min-height: 3;
            max-height: 3;
            padding: 0 1;
            background: $bg;
        }

        #input-box Input {
            border: tall $primary;
            background: $surface;
            color: $primary;
        }

        #input-box Input:focus {
            border: tall $hot;
        }

        #picker-title {
            background: $surface;
            color: $primary;
            padding: 1 2 0 2;
        }

        #picker-list {
            border: solid $primary;
            background: $surface;
            height: auto;
            max-height: 18;
            width: 60;
            align-horizontal: center;
        }

        #welcome {
            height: auto;
            padding: 1 2 0 2;
        }

        #welcome-panel {
            height: auto;
        }

        #welcome-actions {
            height: auto;
            padding: 1 0;
            align: center middle;
        }

        #welcome-actions Button {
            margin: 0 1;
            border: solid $primary;
        }

        #status-bar {
            dock: bottom;
            height: 1;
            background: $surface;
        }

        RichLog {
            padding: 0 1;
        }

        Footer {
            background: $surface;
        }
        """

        BINDINGS = [
            Binding("ctrl+b", "toggle_panel", "Panel", show=True),
            Binding("ctrl+l", "clear_conv", "Clear", show=True),
            Binding("ctrl+d", "app_exit", "Exit", show=True),
            Binding("ctrl+t", "toggle_dark", "Theme", show=True),
            Binding("ctrl+o", "pick_model", "Model", show=True),
            Binding("ctrl+f", "search_conv", "Search", show=True),
            Binding("ctrl+s", "toggle_scroll", "Scroll", show=False),
            Binding("ctrl+y", "copy_last", "Copy", show=True),
            Binding("ctrl+r", "rerun_scan", "Re-run", show=True),
            Binding("escape", "escape_context", "Esc", show=False),
        ]

        show_panel = reactive(False)
        auto_scroll = reactive(True)
        step_mode = reactive(False)

        def __init__(self, agent=None, config=None, **kwargs):
            super().__init__(**kwargs)
            self.agent = agent
            self.config = config
            if isinstance(config, dict):
                theme_name = config.get("theme", "hacker")
            else:
                theme_name = getattr(config, "theme", "hacker") or "hacker"
            self._theme_name = theme_name
            self._tui_pal = tui_palette(theme_name)
            self._last_board_file = ""
            self._last_scan_cmd = ""
            self._processing = False
            self._input_history: list[str] = []
            self._history_idx = -1
            self._spinner_timer: Optional[Timer] = None
            self._tool_start_time = 0.0
            self._process_start_time = 0.0
            self._search_mode = False

        def compose(self) -> ComposeResult:
            pal = self._tui_pal
            provider = self.config.provider if self.config else "?"
            model = self.config.model if self.config else "?"
            header_text = Text()
            header_text.append("  ⚡ ZER0CODE ", style=_st(pal, "primary"))
            header_text.append("│ ", style="dim white")
            header_text.append(f"{provider}/{model} ", style=_st(pal, "accent"))
            header_text.append("│ ", style="dim white")
            header_text.append("OPERATIONAL", style=_st(pal, "primary"))
            yield Static(header_text, id="header-bar")
            yield ContextBreadcrumb(id="breadcrumb")

            with Vertical(id="welcome"):
                yield Static(self._welcome_panel(), id="welcome-panel")
                with Horizontal(id="welcome-actions"):
                    yield Button("⚡ Scan", id="btn-scan", variant="primary")
                    yield Button("🧪 Lab", id="btn-lab")
                    yield Button("📊 Bench", id="btn-bench")
                    yield Button("◢ Theme", id="btn-theme")

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

        def _welcome_panel(self):
            pal = self._tui_pal
            grid = Table(box=None, show_header=False, padding=(0, 3))
            grid.add_column(style="dim")
            grid.add_column(style=_st(pal, "accent"))
            if self.config:
                grid.add_row("Provider", str(getattr(self.config, "provider", "?")))
                grid.add_row("Model", str(getattr(self.config, "model", "?")))
                grid.add_row("Theme", f"{self._theme_name}   (Ctrl+T)")
            if self.agent:
                grid.add_row("Session", (self.agent.session_id or "—")[:12])
                grid.add_row("Arsenal", f"{len(self.agent.tool_registry)} tools · 15 skills")
                budget = getattr(self.agent, "token_budget", 0) or 0
                grid.add_row("Budget", f"${budget:.2f}" if budget else "uncapped")
            hero = Text("⚡ HACK THE PLANET AT MACHINE SPEED ⚡", style=_st(pal, "accent"))
            return Panel(Group(hero, Text(""), grid),
                         title="ZER0CODE // NEON GRID", title_align="left",
                         border_style=pal["primary"], padding=(1, 2))

        def on_button_pressed(self, event: Button.Pressed) -> None:
            bid = event.button.id or ""
            try:
                inp = self.query_one("#user-input", Input)
            except Exception:
                return
            if bid == "btn-scan":
                inp.value = "/scan "
            elif bid == "btn-lab":
                inp.value = "/lab "
            elif bid == "btn-bench":
                inp.value = "/bench"
            elif bid == "btn-theme":
                self._apply_theme("cyberpunk" if self._theme_name != "cyberpunk" else "hacker")
                try:
                    self.query_one("#welcome-panel", Static).update(self._welcome_panel())
                except Exception:
                    pass
                return
            else:
                return
            inp.focus()

        def on_mount(self) -> None:
            pal = self._tui_pal
            conv = self.query_one("#conversation", RichLog)

            try:
                self._render_side_home()
            except Exception:
                pass

            self._update_status()
            self.query_one("#user-input", Input).focus()

        def _render_side_home(self) -> None:
            """Side panel default: live GRID card so it never looks dead."""
            from textual.widgets import RichLog as _RL
            pal = self._tui_pal
            side = self.query_one("#side-panel", _RL)
            side.clear()
            side.write(Text("  ◢ GRID", style=_st(pal, "accent")))
            if self.agent:
                s = self.agent.cost_tracker.summary()
                hist = [h.get("cost", 0) for h in getattr(self.agent.cost_tracker, "_history", [])]
                side.write(Text(f"  spend ${s['total_cost']:.4f} · {s['requests']} req", style="dim"))
                side.write(Text(f"  cost {sparkline(hist) or '—'}", style="dim"))
                side.write(Text(f"  ctx {self.agent.context_window_percent}% · {self.agent.message_count} msgs", style="dim"))
            if getattr(self, "_last_board_file", ""):
                try:
                    from zer0code.swarm import Blackboard
                    board = Blackboard(self._last_board_file)
                    summ = board.summary()
                    score, band = risk_of_severity(summ.get("by_severity", {}))
                    side.write(Text(f"  risk {score} {band} {meter(score / 100, 12)}", style=_st(pal, "warn", bold=False)))
                    side.write(Text(f"  findings {summ.get('total', 0)} ({summ.get('hot', 0)} hot)", style="dim"))
                except Exception:
                    pass
            else:
                side.write(Text("  no campaign yet — /scan <target>", style="dim"))
            side.write(Text("  Ctrl+B close · Esc refocus", style="dim"))

        def _start_spinner(self, action: str = "Thinking") -> None:
            spinner = self.query_one("#spinner-bar", SpinnerWidget)
            spinner.active = True
            spinner.action = action
            try:
                spinner.display = True
            except Exception:
                pass
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
                try:
                    spinner.display = False
                except Exception:
                    pass
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
            pal = self._tui_pal
            if event.input.id != "user-input":
                return
            user_input = event.value.strip()
            if not user_input:
                return
            try:
                self.query_one("#welcome").display = False
            except Exception:
                pass

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
            user_line.append("❯ ", style=_st(pal, "accent"))
            user_line.append(user_input, style="bold white")
            conv.write(user_line)
            conv.write(Text(""))

            if not self.agent:
                conv.write(Panel(Text("Agent not initialized", style="white"), border_style=pal["err"], title="Error"))
                return

            self._processing = True
            self._start_spinner("Thinking")

            def on_tool_call(name, args):
                self.call_from_thread(self._update_spinner_action, f"Running {name}")
                self.call_from_thread(self._show_tool_call, name, args)

            def on_tool_result(name, result, hook_msgs=None):
                pal = self._tui_pal
                self.call_from_thread(self._show_tool_result, name, result)

            self.agent.set_callbacks(on_tool_call=on_tool_call, on_tool_result=on_tool_result)
            self.run_worker(self._run_agent_stream(user_input), thread=True)

        async def _run_agent_stream(self, user_input: str) -> None:
            pal = self._tui_pal
            conv = self.query_one("#conversation", RichLog)
            ts = self._ts()
            collected_text = []
            elapsed = 0.0

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
                        conv.write(Text(f"  {response_text}", style=_st(pal, "primary", bold=False)))

                    cost_line = Text()
                    cost_line.append(f"\n  {self._ts()} ", style="dim")
                    cost_line.append(f"tokens: {self.agent.total_tokens:,}", style=_st(pal, "accent", bold=False, pre="dim "))
                    cost_line.append(f"  │  cost: {self.agent.total_cost}", style=_st(pal, "accent", bold=False, pre="dim "))
                    cost_line.append(f"  │  ctx: {self.agent.context_window_percent}%", style=_st(pal, "accent", bold=False, pre="dim "))
                    elapsed = time.monotonic() - self._process_start_time
                    cost_line.append(f"  │  {elapsed:.1f}s", style="dim")
                    conv.write(cost_line)

            except Exception as e:
                conv.write(Panel(Text(str(e), style="white"), border_style=pal["err"], title=Text("Error", style=_st(pal, "err")), padding=(0, 1)))
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
            pal = self._tui_pal
            conv = self.query_one("#conversation", RichLog)
            ts = self._ts()

            header = Text()
            header.append(f"  {ts} ", style="dim")
            header.append("▶ ", style=_st(pal, "persona"))
            header.append(name, style=_st(pal, "persona"))
            self._tool_start_time = time.monotonic()

            arg_text = Text()
            for k, v in args.items():
                val = str(v)
                if len(val) > 100:
                    val = val[:97] + "..."
                arg_text.append(f"    {k}", style="dim")
                arg_text.append("=", style="white")
                arg_text.append(f"{val}\n", style=_st(pal, "accent", bold=False))

            from rich.console import Group
            panel = Panel(
                Group(header, arg_text),
                border_style=pal["persona"],
                padding=(0, 1),
                expand=True,
            )
            conv.write(panel)

            side = self.query_one("#side-panel", RichLog)
            side.write(Text(f"\n  {ts}  ▶ {name}", style=_st(pal, "persona")))
            for k, v in args.items():
                side.write(Text(f"    {k}={str(v)[:60]}", style="dim"))

        def _show_tool_result(self, name: str, result) -> None:
            pal = self._tui_pal
            conv = self.query_one("#conversation", RichLog)
            ts = self._ts()
            tool_elapsed = time.monotonic() - self._tool_start_time
            success = getattr(result, "success", True)
            output = getattr(result, "output", str(result)) if success else (getattr(result, "error", str(result)) or "Error")

            icon = "✓" if success else "✗"
            style = pal["primary"] if success else pal["err"]

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
            pal = self._tui_pal
            diff_text = Text()
            for line in output.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    diff_text.append(line + "\n", style=_st(pal, "primary", bold=False))
                elif line.startswith("-") and not line.startswith("---"):
                    diff_text.append(line + "\n", style=_st(pal, "err", bold=False))
                elif line.startswith("@@"):
                    diff_text.append(line + "\n", style=_st(pal, "accent", bold=False))
                else:
                    diff_text.append(line + "\n", style="dim")
            panel = Panel(diff_text, border_style=pal["accent"], title=title, title_align="left", padding=(0, 1), expand=True)
            conv.write(panel)

        def _do_search(self, query: str) -> None:
            pal = self._tui_pal
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
                conv.write(Text(f"  No matches for '{query}'", style=_st(pal, "warn", bold=False, pre="dim ")))
            else:
                conv.write(Text(f"  {matches} match(es) found", style=_st(pal, "primary", bold=False, pre="dim ")))

        async def _handle_slash(self, cmd: str, conv: RichLog) -> None:
            pal = self._tui_pal
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
                    ("/model", "Pick model (list)"),
                    ("/provider", "Pick provider (list)"),
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
                    ("/theme", "Cycle/set theme"),
                    ("/scan <t>", "Swarm hunt a target"),
                    ("/lab list|up|down", "Vuln labs"),
                    ("/bench", "Benchmark score"),
                    ("Ctrl+B", "Toggle side panel"),
                    ("Ctrl+F", "Search conversation"),
                    ("Ctrl+L", "Clear"),
                    ("Ctrl+T", "Cycle theme"),
                    ("Ctrl+O", "Pick model"),
                    ("Ctrl+D", "Exit"),
                    ("Up/Down", "Input history"),
                ]
                conv.write(Text("\n  ZER0CODE Commands\n", style=_st(pal, "primary")))
                for c, d in help_cmds:
                    line = Text()
                    line.append(f"  {c:<22}", style=_st(pal, "accent"))
                    line.append(d, style="dim")
                    conv.write(line)
                conv.write(Text(""))

            elif command == "/clear":
                conv.clear()
                if self.agent:
                    self.agent.reset()
                conv.write(Text("  Conversation cleared.\n", style=_st(pal, "primary")))

            elif command == "/tools":
                if self.agent:
                    conv.write(Text("\n  Registered Tools\n", style=_st(pal, "persona")))
                    for name, tool in sorted(self.agent.tool_registry.items()):
                        desc = getattr(tool, "description", "")[:50]
                        line = Text()
                        line.append(f"  {name:<22}", style=_st(pal, "persona"))
                        line.append(desc, style="dim")
                        conv.write(line)
                    conv.write(Text(f"\n  {len(self.agent.tool_registry)} tools\n", style="dim"))

            elif command == "/status":
                self._update_status()
                if self.agent:
                    conv.write(Text(f"  Tokens: {self.agent.total_tokens:,} | Cost: {self.agent.total_cost} | Context: {self.agent.context_window_percent}% | Messages: {self.agent.message_count}", style=_st(pal, "accent", bold=False)))

            elif command == "/config":
                if self.config:
                    for k, v in [("Provider", self.config.provider), ("Model", self.config.model), ("Theme", self.config.theme), ("Memory", str(self.config.memory_enabled)), ("Session", self.agent.session_id if self.agent else "N/A")]:
                        conv.write(Text(f"  {k}: {v}", style=_st(pal, "accent", bold=False)))

            elif command == "/model":
                if args and self.config:
                    self.config.model = args.strip()
                    try:
                        self.config.save()
                    except Exception:
                        pass
                    conv.write(Text(f"  Model → {self.config.model}", style=_st(pal, "primary")))
                    self._update_status()
                    self._update_header()
                elif self.config:
                    self._open_model_picker()
                else:
                    conv.write(Text(f"  Current: {self.config.model if self.config else '?'}", style="dim"))

            elif command == "/provider":
                if args and self.config:
                    from zer0code.providers import PROVIDERS
                    p = args.strip().lower()
                    if p in PROVIDERS:
                        self.config.provider = p
                        try:
                            self.config.save()
                        except Exception:
                            pass
                        conv.write(Text(f"  Provider → {p}", style=_st(pal, "primary")))
                        self._update_status()
                        self._update_header()
                    else:
                        conv.write(Text(f"  Valid: {', '.join(sorted(PROVIDERS))}", style=_st(pal, "err", bold=False)))
                elif self.config:
                    self._open_provider_picker()
                else:
                    conv.write(Text(f"  Current: {self.config.provider if self.config else '?'}", style="dim"))

            elif command == "/cost":
                if self.agent:
                    s = self.agent.cost_tracker.summary()
                    conv.write(Text(f"  Total: {s['total_tokens']:,} tokens (in: {s['input_tokens']:,}, out: {s['output_tokens']:,})", style=_st(pal, "accent", bold=False)))
                    conv.write(Text(f"  Cost: {self.agent.total_cost} | Requests: {s['requests']}", style=_st(pal, "accent", bold=False)))

            elif command == "/compact":
                if self.agent and self.agent.compactor:
                    old = len(self.agent.conversation_history)
                    self.agent.conversation_history = await self.agent.compactor.compact(self.agent.conversation_history)
                    conv.write(Text(f"  Compacted: {old} → {len(self.agent.conversation_history)} messages", style=_st(pal, "primary")))
                else:
                    conv.write(Text("  Nothing to compact (agent not ready).", style="dim"))

            elif command == "/export":
                if self.agent:
                    filepath = args.strip() if args else f"zer0code-report-{int(time.time())}.md"
                    fmt = "html" if filepath.endswith(".html") else "md"
                    metadata = {"provider": self.config.provider if self.config else "", "model": self.config.model if self.config else "", "session_id": self.agent.session_id}
                    saved = self.agent.exporter.save(self.agent.conversation_history, filepath, format=fmt, metadata=metadata)
                    conv.write(Text(f"  Exported → {saved}", style=_st(pal, "primary")))

            elif command == "/skill":
                from zer0code.skills.loader import SkillLoader
                loader = SkillLoader()
                if not args:
                    for cat, skills in loader.list_by_category().items():
                        conv.write(Text(f"\n  {cat}", style=_st(pal, "persona")))
                        for sk in skills:
                            conv.write(Text(f"    {sk['name']:<22} {sk.get('description', '')[:40]}", style="dim"))
                    conv.write(Text(f"\n  {loader.count} skills | /skill <name> to load\n", style="dim"))
                else:
                    skill = loader.get_skill(args.strip())
                    if skill and self.agent:
                        self.agent.conversation_history.append({"role": "system", "content": f"LOADED SKILL: {skill.get('title', skill['name'])}\n\n{skill['system_prompt_addition']}"})
                        conv.write(Text(f"  Loaded: {skill.get('title', skill['name'])} ({skill.get('lines', '?')} lines)", style=_st(pal, "primary")))
                        self._update_breadcrumb(skill_name=args.strip())
                    else:
                        conv.write(Text(f"  Not found: {args.strip()}", style=_st(pal, "err", bold=False)))

            elif command == "/persona":
                from zer0code.personas import PersonaManager
                pm = PersonaManager()
                if args and self.agent:
                    persona = pm.get_persona(args.strip())
                    if persona:
                        self.agent.conversation_history.append({"role": "system", "content": persona.system_prompt})
                        conv.write(Text(f"  Persona → {persona.title}", style=_st(pal, "primary")))
                        self._update_breadcrumb(persona_name=args.strip())
                    else:
                        conv.write(Text(f"  Available: {', '.join(pm.list_personas())}", style="dim"))
                else:
                    for name in pm.list_personas():
                        p = pm.get_persona(name)
                        conv.write(Text(f"  {name:<16} {p.title}", style="dim"))

            elif command == "/template":
                from zer0code.templates import TemplateManager
                tm = TemplateManager()
                if not args:
                    conv.write(Text("\n  Prompt Templates\n", style=_st(pal, "accent")))
                    for tname, desc in tm.list_templates():
                        line = Text()
                        line.append(f"  {tname:<22}", style=_st(pal, "accent"))
                        line.append(desc[:60], style="dim")
                        conv.write(line)
                    conv.write(Text("  Usage: /template <name> <target>", style="dim"))
                else:
                    parts = args.strip().split(maxsplit=1)
                    tpl_name = parts[0]
                    tpl_args = parts[1] if len(parts) > 1 else ""
                    try:
                        rendered = tm.render(tpl_name, target=tpl_args, input=tpl_args)
                    except ValueError as e:
                        conv.write(Text(f"  Template error: {e}", style=_st(pal, "err", bold=False)))
                        return
                    if rendered:
                        conv.write(Text(f"  Running template: {tpl_name}", style=_st(pal, "accent")))
                        await self._run_agent_stream(rendered)
                    else:
                        conv.write(Text(f"  Template '{tpl_name}' not found.", style=_st(pal, "err", bold=False)))

            elif command == "/session":
                sm = self.agent.session_manager if self.agent else None
                if sm is None:
                    conv.write(Text("  Sessions unavailable (agent not ready).", style="dim"))
                elif not args or args == "list":
                    sessions = await sm.list_sessions()
                    if sessions:
                        for s in sessions:
                            from datetime import datetime as _dt
                            upd = _dt.fromtimestamp(s.updated_at).strftime("%m-%d %H:%M")
                            cur = " ◀" if self.agent and s.session_id == self.agent.session_id else ""
                            conv.write(Text(f"  {s.session_id:<10} {s.title[:30]:<30} {s.message_count:>3} msgs {upd}{cur}", style="dim"))
                    else:
                        conv.write(Text("  No sessions found.", style="dim"))
                elif args.startswith("load ") and self.agent:
                    sid = args[5:].strip()
                    if await self.agent.load_session(sid):
                        conv.write(Text(f"  Loaded {sid} ({self.agent.message_count} messages)", style=_st(pal, "primary")))
                    else:
                        conv.write(Text(f"  Session {sid} not found.", style=_st(pal, "err", bold=False)))
                elif args.startswith("title ") and self.agent and self.agent.session_id:
                    await sm.update_title(self.agent.session_id, args[6:].strip())
                    conv.write(Text(f"  Title updated.", style=_st(pal, "primary")))
                elif args.startswith("delete "):
                    await sm.delete_session(args[7:].strip())
                    conv.write(Text(f"  Deleted {args[7:].strip()}.", style=_st(pal, "primary")))
                else:
                    conv.write(Text("  Usage: /session list|load <id>|title <name>|delete <id>", style="dim"))

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
                    st = pal["primary"] if s == "pass" else pal["warn"] if s == "warn" else pal["err"]
                    conv.write(Text(f"  {icon} {check['name']:<18} {check['detail']}", style=st))
                conv.write(Text(f"\n  {doc.summary}\n", style="dim"))

            elif command == "/init":
                from zer0code.init_project import ProjectInitializer
                from pathlib import Path
                pi = ProjectInitializer()
                fp = pi.save()
                conv.write(Text(f"  Generated → {fp}", style=_st(pal, "primary")))

            elif command == "/files":
                if self.agent and self.agent.file_index:
                    if args:
                        for r in self.agent.file_index.search(args.strip())[:20]:
                            conv.write(Text(f"  {r}", style="dim"))
                    else:
                        conv.write(Text(self.agent.file_index.get_tree(), style="dim"))

            elif command == "/step":
                self.step_mode = not self.step_mode
                conv.write(Text(f"  Step mode: {'ON' if self.step_mode else 'OFF'}", style=_st(pal, "primary")))

            elif command == "/theme":
                order = ["hacker", "cyberpunk", "dark", "minimal"]
                if args and args.strip().lower() in TUI_PALETTES:
                    name = args.strip().lower()
                else:
                    cur = getattr(self.config, "theme", "hacker") if self.config else "hacker"
                    name = order[(order.index(cur) + 1) % len(order)] if cur in order else "cyberpunk"
                self._apply_theme(name)
                conv.write(Text(f"  Theme → {name} (saved)", style=_st(pal, "primary")))
                pal = self._tui_pal

            elif command == "/budget":
                if args and self.agent:
                    try:
                        self.agent.token_budget = float(args.strip().replace("$", ""))
                        conv.write(Text(f"  Budget → ${self.agent.token_budget:.2f}", style=_st(pal, "primary")))
                    except ValueError:
                        conv.write(Text("  Usage: /budget <amount>", style="dim"))
                elif self.agent:
                    conv.write(Text(f"  Budget: ${self.agent.token_budget:.2f} | Spent: {self.agent.total_cost}", style="dim"))

            elif command == "/undo":
                if self.agent:
                    if args == "all":
                        restored = self.agent.rollback.rollback_all()
                        conv.write(Text(f"  Restored {len(restored)} files", style=_st(pal, "primary")))
                    elif args == "list":
                        for c in self.agent.rollback.list_changes():
                            conv.write(Text(f"  {c['filepath']}", style="dim"))
                    elif args:
                        if self.agent.rollback.rollback(args.strip()):
                            conv.write(Text(f"  Restored: {args.strip()}", style=_st(pal, "primary")))
                        else:
                            conv.write(Text(f"  No snapshot for: {args.strip()}", style=_st(pal, "err", bold=False)))
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
                        conv.write(Text(f"  Branch created → {name}", style=_st(pal, "primary")))
                        self._update_breadcrumb(branch_name=name)
                    elif args.startswith("switch "):
                        if self.agent.brancher.switch_branch(args[7:].strip()):
                            self.agent.conversation_history = self.agent.brancher.current_messages
                            conv.write(Text(f"  Switched → {args[7:].strip()}", style=_st(pal, "primary")))
                            self._update_breadcrumb(branch_name=args[7:].strip())
                        else:
                            conv.write(Text(f"  Branch not found: {args[7:].strip()}", style=_st(pal, "err", bold=False)))
                    else:
                        conv.write(Text("  Usage: /branch list|create <name>|switch <name>", style="dim"))

            elif command in ("/exit", "/quit"):
                self.exit()

            elif command == "/copy":
                self.action_copy_last()

            elif command == "/scan":
                from zer0code.headless import run_headless_scan
                if not args:
                    conv.write(Text("  Usage: /scan <target> [--scope s] [--rounds N] [--no-swarm] [--jev]", style="dim"))
                else:
                    toks = args.split()
                    target = toks[0]
                    scope, rounds, mode, jev = target, 6, "swarm", False
                    it = iter(toks[1:])
                    bad = False
                    for t in it:
                        if t == "--scope":
                            scope = next(it, scope)
                        elif t == "--rounds":
                            try:
                                rounds = int(next(it, rounds))
                            except ValueError:
                                conv.write(Text("  --rounds needs a number", style=_st(pal, "err", bold=False)))
                                bad = True
                        elif t == "--no-swarm":
                            mode = "sequential"
                        elif t == "--jev":
                            jev = True
                    if not bad:
                        from zer0code.scope import ScopeManager as _SM
                        _sm = _SM()
                        for _s in [p.strip() for p in scope.split(",") if p.strip()]:
                            _sm.add_in_scope(_s)
                        if not _sm.is_in_scope(target):
                            conv.write(Text(f"  Target '{target}' is OUT OF SCOPE", style=_st(pal, "err", bold=False)))
                        else:
                            conv.write(Text(f"  Hunting {target} [{mode}]…", style=_st(pal, "accent")))
                            from textual.widgets import RichLog as _RL
                            try:
                                _side = self.query_one("#side-panel", _RL)
                                _side.clear()
                                if not self.show_panel:
                                    self.show_panel = True
                                    _side.add_class("visible")
                            except Exception:
                                _side = None

                            def _progress(rno, fired, board, _side=_side, _pal=pal):
                                if _side is None:
                                    return
                                try:
                                    total = len(board.all())
                                    confirmed = sum(1 for f in board.all()
                                                    if f.ftype == "VULN_CONFIRMED")
                                    _side.clear()
                                    _side.write(Text(f"  NOW ▸ round {rno + 1}: {total} findings ({confirmed} confirmed)", style=_st(_pal, "primary")))
                                    pills = " → ".join(
                                        f"{'✓' if fired.get(a) else '·'}{a}"
                                        for a in ("recon", "classify", "exploit", "report"))
                                    _side.write(Text(f"  {pills}", style="dim"))
                                    sev = board.summary().get("by_severity", {})
                                    _side.write(Text("  " + " ".join(
                                        f"{k}:{sev.get(k, 0)}" for k in ("critical", "high", "medium", "low", "info")), style="dim"))
                                    for f in board.all()[-4:]:
                                        _side.write(Text(f"  ● [{f.severity}] {f.title[:60]}", style="dim"))
                                except Exception:
                                    pass

                            try:
                                result, board_file = await run_headless_scan(
                                    target, scope=scope, rounds=rounds, mode=mode, jev=jev,
                                    on_event=_progress)
                                self._last_board_file = board_file
                                self._last_scan_cmd = f"/scan {args}"
                                _rword = "round" if result.rounds == 1 else "rounds"
                                conv.write(Text(f"  Done: {result.rounds} {_rword}, {result.findings_total} findings, "
                                                f"{result.confirmed} confirmed ({result.stopped_reason})", style=_st(pal, "primary")))
                                conv.write(Text(f"  Board: {board_file}  ·  Ctrl+R re-run", style="dim"))
                                try:
                                    self._render_side_home()
                                except Exception:
                                    pass
                            except PermissionError as e:
                                conv.write(Text(f"  {e}", style=_st(pal, "err", bold=False)))
                            except Exception as e:
                                conv.write(Text(f"  Scan failed: {e}", style=_st(pal, "err", bold=False)))

            elif command == "/lab":
                from zer0code.lab import LabManager
                mgr = LabManager()
                sub = (args or "list").split()
                if sub[0] == "list":
                    for spec in mgr.list_labs():
                        conv.write(Text(f"  {spec.name:<8} {spec.description} (:{spec.port})", style="dim"))
                elif sub[0] in ("up", "down") and len(sub) > 1:
                    try:
                        if sub[0] == "up":
                            url = await mgr.up(sub[1])
                            conv.write(Text(f"  {sub[1]} up at {url}", style=_st(pal, "primary")))
                        else:
                            await mgr.down(sub[1])
                            conv.write(Text(f"  {sub[1]} down", style=_st(pal, "primary")))
                    except Exception as e:
                        conv.write(Text(f"  lab failed: {e}", style=_st(pal, "err", bold=False)))
                else:
                    conv.write(Text("  Usage: /lab list|up <name>|down <name>", style="dim"))

            elif command == "/bench":
                from zer0code.bench import run_offline, run_suite
                if "--suite" in args and "mini" in args:
                    res = run_suite("mini")
                    conv.write(Text(f"  Mini-suite: {res['passed']}/{res['total']} (score {res['score']})", style=_st(pal, "primary")))
                else:
                    res = await run_offline()
                    conv.write(Text(f"  Bench score: {res['score']} (detection {res['detection']}, precision {res['precision']})", style=_st(pal, "primary")))

            else:
                conv.write(Text(f"  Unknown: {command}  — type /help", style=_st(pal, "warn", bold=False)))

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

        def action_escape_context(self) -> None:
            """ESC: close side panel if open, else refocus the input."""
            try:
                if self.show_panel:
                    self.show_panel = False
                    self.query_one("#side-panel").remove_class("visible")
            except Exception:
                pass
            try:
                self.query_one("#user-input", Input).focus()
            except Exception:
                pass
            try:
                self._log_esc_state()
            except Exception:
                pass
            try:
                self.refresh(layout=True)
            except Exception:
                pass

        def _log_esc_state(self) -> None:
            """Best-effort ESC forensics: visibility snapshot to a log file."""
            import datetime
            from pathlib import Path
            states = {}
            for wid in ("#welcome", "#main-area", "#header-bar",
                        "#conversation", "#input-box", "#side-panel"):
                try:
                    w = self.query_one(wid)
                    states[wid] = bool(w.display)
                except Exception as e:
                    states[wid] = f"ERR:{type(e).__name__}"
            line = (f"{datetime.datetime.now().isoformat()} esc "
                    f"screens={[type(s).__name__ for s in self.screen_stack]} "
                    f"{states}\n")
            log = Path.home() / ".zer0code" / "tui-debug.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a") as fh:
                fh.write(line)

        def action_rerun_scan(self) -> None:
            """Ctrl+R: re-run the last /scan with identical args."""
            cmd = getattr(self, "_last_scan_cmd", "")
            if not cmd:
                return
            try:
                conv = self.query_one("#conversation", RichLog)
            except Exception:
                return
            self.run_worker(self._handle_slash(cmd, conv))

        def action_clear_conv(self) -> None:
            conv = self.query_one("#conversation", RichLog)
            conv.clear()
            if self.agent:
                self.agent.reset()

        def action_app_exit(self) -> None:
            self.exit()

        def _provider_models(self) -> list[str]:
            try:
                from zer0code.providers import PROVIDERS
                cls = PROVIDERS.get((self.config.provider if self.config else "openai"), None)
                if cls is None:
                    return []
                return list(cls().available_models)
            except Exception:
                return []

        def _open_model_picker(self) -> None:
            models = self._provider_models()
            if not models:
                return
            self.push_screen(PickerScreen("MODEL", models), self._on_model_picked)

        def _on_model_picked(self, result) -> None:
            if result and self.config:
                self.config.model = result
                try:
                    self.config.save()
                except Exception:
                    pass
                try:
                    self._update_header()
                    self._update_status()
                except Exception:
                    pass
                try:
                    conv = self.query_one("#conversation", RichLog)
                    conv.write(Text(f"  Model → {result}", style=_st(self._tui_pal, "primary")))
                except Exception:
                    pass

        def _open_provider_picker(self) -> None:
            try:
                from zer0code.providers import PROVIDERS
                options = sorted(PROVIDERS)
            except Exception:
                return
            self.push_screen(PickerScreen("PROVIDER", options), self._on_provider_picked)

        def _on_provider_picked(self, result) -> None:
            if result and self.config:
                self.config.provider = result
                try:
                    self.config.save()
                except Exception:
                    pass
                try:
                    self._update_header()
                    self._update_status()
                except Exception:
                    pass
                try:
                    conv = self.query_one("#conversation", RichLog)
                    conv.write(Text(f"  Provider → {result}", style=_st(self._tui_pal, "primary")))
                except Exception:
                    pass

        def _apply_theme(self, name: str) -> None:
            """Switch named neon theme live (chrome CSS + content palette)."""
            self._theme_name = name
            self._tui_pal = tui_palette(name)
            ZeroCodeTUI.CSS = build_tui_css(ZeroCodeTUI._CSS_TEMPLATE, self._tui_pal)
            try:
                self.refresh_css()
            except Exception:
                pass
            if self.config and hasattr(self.config, "theme"):
                self.config.theme = name
                try:
                    self.config.save()
                except Exception:
                    pass
            try:
                self._update_header()
            except Exception:
                pass

        def action_toggle_dark(self) -> None:
            order = ["hacker", "cyberpunk", "dark", "minimal"]
            cur = getattr(self.config, "theme", "hacker") if self.config else "hacker"
            nxt = order[(order.index(cur) + 1) % len(order)] if cur in order else "cyberpunk"
            self._apply_theme(nxt)

        def action_pick_model(self) -> None:
            self._open_model_picker()

        def action_search_conv(self) -> None:
            self._search_mode = True
            inp = self.query_one("#user-input", Input)
            inp.placeholder = "  🔍 Search conversation (Enter to search, type query)..."
            inp.focus()

        def action_toggle_scroll(self) -> None:
            self.auto_scroll = not self.auto_scroll
            conv = self.query_one("#conversation", RichLog)
            conv.auto_scroll = self.auto_scroll

        def action_copy_last(self) -> None:
            pal = self._tui_pal
            if not self.agent:
                return
            last_response = ""
            for msg in reversed(self.agent.conversation_history):
                if msg.get("role") == "assistant" and msg.get("content"):
                    last_response = msg["content"]
                    break
            if last_response:
                import subprocess
                import sys
                try:
                    if sys.platform == "darwin":
                        subprocess.run(["pbcopy"], input=last_response.encode(), check=True)
                    elif sys.platform == "linux":
                        for cmd in ["xclip -selection clipboard", "xsel --clipboard --input", "wl-copy"]:
                            try:
                                subprocess.run(cmd.split(), input=last_response.encode(), check=True, capture_output=True)
                                break
                            except Exception:
                                continue
                    elif sys.platform == "win32":
                        subprocess.run(["clip"], input=last_response.encode(), check=True)
                except Exception:
                    pass
                conv = self.query_one("#conversation", RichLog)
                conv.write(Text(f"  Copied {len(last_response)} chars to clipboard", style=_st(pal, "primary")))

        def _update_header(self) -> None:
            pal = self._tui_pal
            try:
                header = self.query_one("#header-bar", Static)
                ht = Text()
                ht.append("  ⚡ ZER0CODE ", style=_st(pal, "primary"))
                ht.append("│ ", style="dim white")
                if self.config:
                    ht.append(f"{self.config.provider}/{self.config.model} ", style=_st(pal, "accent"))
                ht.append("│ ", style="dim white")
                ht.append("OPERATIONAL", style=_st(pal, "primary"))
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
    if isinstance(config, dict):
        theme_name = config.get("theme", "hacker")
    else:
        theme_name = getattr(config, "theme", "hacker") or "hacker"
    pal = tui_palette(theme_name)
    ZeroCodeTUI.CSS = build_tui_css(ZeroCodeTUI._CSS_TEMPLATE, pal)
    app = ZeroCodeTUI(agent=agent, config=config)
    app.run()
    return True
