import os
import time
import asyncio
from typing import Optional, AsyncGenerator

from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich.align import Align

from truthzero.ui.themes import Theme, THEMES


GRADIENT_BAR = "  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"

BANNER_LINES = [
    "   TRUTHZERO  //  HACK THE PLANET AT MACHINE SPEED",
]

VERSION = "0.2.0"
TAGLINE = "Autonomous Pentesting Agent"


class Banner:
    def __init__(self, theme: Theme, provider: str = "", model: str = ""):
        self.theme = theme
        self.provider = provider
        self.model = model

    def render(self, console: Console) -> None:
        output = Text()

        output.append(f"\n{GRADIENT_BAR}\n\n", style="bold green")

        for line in BANNER_LINES:
            output.append(f"{line}\n", style="bold bright_green")

        output.append(f"\n{GRADIENT_BAR}\n", style="bold green")

        tagline = Text()
        tagline.append("\n          \u26a1 ", style="bold yellow")
        tagline.append(TAGLINE.upper(), style="bold cyan")
        tagline.append(f"  v{VERSION}", style="dim white")
        tagline.append("  \u26a1", style="bold yellow")

        provider_line = Text()
        if self.provider or self.model:
            provider_line.append("\n")
            if self.provider:
                provider_line.append("          Provider: ", style="dim")
                provider_line.append(self.provider, style=self.theme.accent)
            if self.model:
                if self.provider:
                    provider_line.append("  \u2502  ", style="dim")
                provider_line.append("Model: ", style="dim")
                provider_line.append(self.model, style=self.theme.accent)

        content = Group(output, tagline, provider_line)

        panel = Panel(
            content,
            border_style="bright_green",
            padding=(0, 2),
            expand=False,
        )
        console.print(panel)


class ToolPanel:
    def __init__(self, theme: Theme):
        self.theme = theme

    def render_call(self, console: Console, name: str, args: dict) -> None:
        header = Text()
        header.append("\u25b6 ", style=self.theme.accent)
        header.append(name, style=self.theme.tool_name)

        arg_lines = Text()
        for key, value in args.items():
            arg_lines.append(f"  {key}", style=self.theme.muted)
            arg_lines.append("=", style=self.theme.fg)
            display_val = str(value)
            if len(display_val) > 120:
                display_val = display_val[:117] + "..."
            arg_lines.append(f"{display_val}\n", style=self.theme.tool_output)

        content = Group(header, arg_lines)
        panel = Panel(
            content,
            border_style=self.theme.border,
            title=Text("Tool Call", style=self.theme.tool_name),
            title_align="left",
            padding=(0, 1),
        )
        console.print(panel)

    def render_spinner(self, console: Console, name: str) -> Live:
        spinner_text = Text()
        spinner_text.append(f"  Running {name}...", style=self.theme.muted)

        spinner = Spinner("dots", text=spinner_text, style=self.theme.accent)
        live = Live(spinner, console=console, refresh_per_second=12)
        return live

    def render_result(
        self, console: Console, name: str, result: str, success: bool = True
    ) -> None:
        status_style = self.theme.success if success else self.theme.error
        status_icon = "\u2713" if success else "\u2717"

        header = Text()
        header.append(f" {status_icon} ", style=status_style)
        header.append(name, style=self.theme.tool_name)

        if self._looks_like_code(result):
            lang = self._detect_language(result)
            result_display = Syntax(
                result,
                lang,
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
            )
        else:
            result_display = Text(result, style=self.theme.tool_output)

        content = Group(header, Text(), result_display)
        border = self.theme.success if success else self.theme.error
        panel = Panel(
            content,
            border_style=border,
            title=Text("Result", style=status_style),
            title_align="left",
            padding=(0, 1),
        )
        console.print(panel)

    def _looks_like_code(self, text: str) -> bool:
        indicators = [
            "def ", "class ", "import ", "from ",
            "function ", "const ", "let ", "var ",
            "#!/", "<?php", "<html", "SELECT ",
            "{", "}", "=>", "->",
        ]
        count = sum(1 for i in indicators if i in text)
        return count >= 2

    def _detect_language(self, text: str) -> str:
        if "def " in text or "import " in text:
            return "python"
        if "function " in text or "const " in text:
            return "javascript"
        if "<?php" in text:
            return "php"
        if "<html" in text:
            return "html"
        if "SELECT " in text or "INSERT " in text:
            return "sql"
        return "text"


class MemoryPanel:
    def __init__(self, theme: Theme):
        self.theme = theme

    def render(self, console: Console, memories: list[dict]) -> None:
        if not memories:
            console.print(
                Text("  No memories stored yet.", style=self.theme.muted)
            )
            return

        table = Table(
            border_style=self.theme.border,
            show_header=True,
            header_style=self.theme.primary,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("#", style=self.theme.muted, width=4)
        table.add_column("Category", style=self.theme.accent, width=14)
        table.add_column("Content", style=self.theme.fg)
        table.add_column("Source", style=self.theme.muted, width=20)

        for idx, mem in enumerate(memories, 1):
            content = str(mem.get("content", ""))
            if len(content) > 80:
                content = content[:77] + "..."
            table.add_row(
                str(idx),
                mem.get("category", "general"),
                content,
                mem.get("source", "manual"),
            )

        panel = Panel(
            table,
            border_style=self.theme.border,
            title=Text("\U0001f9e0 Memory Store", style=self.theme.primary),
            title_align="left",
        )
        console.print(panel)


class StatusBar:
    def __init__(self, theme: Theme):
        self.theme = theme

    def render(
        self,
        console: Console,
        model: str = "",
        provider: str = "",
        tokens: int = 0,
        memories: int = 0,
        cwd: Optional[str] = None,
    ) -> None:
        bar = Text()

        bar.append(" \u2588 ", style=self.theme.accent)
        bar.append(provider or "none", style=self.theme.primary)
        bar.append("/", style=self.theme.muted)
        bar.append(model or "none", style=self.theme.primary)

        bar.append("  \u2502  ", style=self.theme.muted)
        bar.append("tokens: ", style=self.theme.muted)
        bar.append(f"{tokens:,}", style=self.theme.accent)

        bar.append("  \u2502  ", style=self.theme.muted)
        bar.append("memories: ", style=self.theme.muted)
        bar.append(str(memories), style=self.theme.accent)

        bar.append("  \u2502  ", style=self.theme.muted)
        bar.append("cwd: ", style=self.theme.muted)
        display_cwd = cwd or os.getcwd()
        home = os.path.expanduser("~")
        if display_cwd.startswith(home):
            display_cwd = "~" + display_cwd[len(home):]
        bar.append(display_cwd, style=self.theme.fg)

        rule = Rule(style=self.theme.muted)
        console.print(rule)
        console.print(bar)


class ResponseRenderer:
    def __init__(self, theme: Theme):
        self.theme = theme
        self.console = Console()

    def render_markdown(self, console: Console, text: str) -> None:
        md = Markdown(
            text,
            code_theme="monokai",
            inline_code_lexer="python",
            inline_code_theme="monokai",
        )
        console.print(md)

    def render_code(
        self, console: Console, code: str, language: str = "python"
    ) -> None:
        syntax = Syntax(
            code,
            language,
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
            padding=1,
        )
        panel = Panel(
            syntax,
            border_style=self.theme.border,
            title=Text(language, style=self.theme.accent),
            title_align="right",
            padding=(0, 0),
        )
        console.print(panel)

    async def render_stream(
        self, console: Console, token_generator: AsyncGenerator[str, None]
    ) -> str:
        full_text = []
        buffer = []
        last_flush = time.monotonic()
        flush_interval = 0.05

        with Live(
            Text("", style=self.theme.fg),
            console=console,
            refresh_per_second=20,
            vertical_overflow="visible",
        ) as live:
            async for token in token_generator:
                full_text.append(token)
                buffer.append(token)

                now = time.monotonic()
                if now - last_flush >= flush_interval or token.endswith("\n"):
                    current_text = "".join(full_text)
                    if self._contains_code_block(current_text):
                        display = self._render_partial_markdown(current_text)
                    else:
                        display = Text(current_text, style=self.theme.fg)
                    live.update(display)
                    buffer.clear()
                    last_flush = now

            final_text = "".join(full_text)
            if self._contains_code_block(final_text):
                display = Markdown(
                    final_text,
                    code_theme="monokai",
                    inline_code_lexer="python",
                    inline_code_theme="monokai",
                )
            else:
                display = Text(final_text, style=self.theme.fg)
            live.update(display)

        return final_text

    def _contains_code_block(self, text: str) -> bool:
        return "```" in text

    def _render_partial_markdown(self, text: str) -> Markdown:
        fence_count = text.count("```")
        if fence_count % 2 != 0:
            text = text + "\n```"
        return Markdown(
            text,
            code_theme="monokai",
            inline_code_lexer="python",
            inline_code_theme="monokai",
        )
