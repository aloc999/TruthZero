import difflib

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.syntax import Syntax


class DiffRenderer:
    @staticmethod
    def render_diff(
        console: Console,
        old_content: str,
        new_content: str,
        filename: str = "",
    ) -> None:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )

        diff_text = Text()
        for line in diff:
            line_str = line.rstrip("\n")
            if line_str.startswith("+") and not line_str.startswith("+++"):
                diff_text.append(line_str + "\n", style="green")
            elif line_str.startswith("-") and not line_str.startswith("---"):
                diff_text.append(line_str + "\n", style="red")
            elif line_str.startswith("@@"):
                diff_text.append(line_str + "\n", style="cyan")
            elif line_str.startswith("---") or line_str.startswith("+++"):
                diff_text.append(line_str + "\n", style="bold")
            else:
                diff_text.append(line_str + "\n", style="dim")

        if not diff_text.plain.strip():
            console.print(Text("  No changes", style="dim"))
            return

        panel = Panel(
            diff_text,
            border_style="cyan",
            title=Text(f"Changes: {filename}", style="bold cyan") if filename else None,
            title_align="left",
            padding=(0, 1),
        )
        console.print(panel)

    @staticmethod
    def render_edit(
        console: Console,
        old_string: str,
        new_string: str,
        filename: str = "",
    ) -> None:
        diff_text = Text()
        diff_text.append("- ", style="red")
        diff_text.append(old_string.rstrip("\n") + "\n", style="red")
        diff_text.append("+ ", style="green")
        diff_text.append(new_string.rstrip("\n") + "\n", style="green")

        panel = Panel(
            diff_text,
            border_style="cyan",
            title=Text(f"Edit: {filename}", style="bold cyan") if filename else None,
            title_align="left",
            padding=(0, 1),
        )
        console.print(panel)
