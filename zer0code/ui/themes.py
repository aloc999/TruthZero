from dataclasses import dataclass, field
from rich.style import Style


@dataclass
class Theme:
    name: str
    primary: Style
    secondary: Style
    accent: Style
    error: Style
    warning: Style
    success: Style
    muted: Style
    bg: Style
    fg: Style
    border: Style
    tool_name: Style
    tool_output: Style
    code_bg: Style
    prompt_symbol: str
    prompt_color: Style

    def __post_init__(self):
        self._styles = {
            "primary": self.primary,
            "secondary": self.secondary,
            "accent": self.accent,
            "error": self.error,
            "warning": self.warning,
            "success": self.success,
            "muted": self.muted,
            "bg": self.bg,
            "fg": self.fg,
            "border": self.border,
            "tool_name": self.tool_name,
            "tool_output": self.tool_output,
            "code_bg": self.code_bg,
            "prompt_color": self.prompt_color,
        }

    def get(self, name: str) -> Style:
        return self._styles.get(name, self.fg)


THEMES = {
    "hacker": Theme(
        name="hacker",
        primary=Style(color="green", bold=True),
        secondary=Style(color="bright_green"),
        accent=Style(color="cyan", bold=True),
        error=Style(color="red", bold=True),
        warning=Style(color="yellow"),
        success=Style(color="bright_green", bold=True),
        muted=Style(color="bright_black"),
        bg=Style(bgcolor="grey3"),
        fg=Style(color="green"),
        border=Style(color="green"),
        tool_name=Style(color="cyan", bold=True),
        tool_output=Style(color="bright_green"),
        code_bg=Style(bgcolor="grey7", color="bright_green"),
        prompt_symbol="\u276f",
        prompt_color=Style(color="bright_green", bold=True),
    ),
    "dark": Theme(
        name="dark",
        primary=Style(color="bright_blue", bold=True),
        secondary=Style(color="medium_purple1"),
        accent=Style(color="deep_sky_blue1", bold=True),
        error=Style(color="red1", bold=True),
        warning=Style(color="orange1"),
        success=Style(color="green3", bold=True),
        muted=Style(color="grey58"),
        bg=Style(bgcolor="grey11"),
        fg=Style(color="grey84"),
        border=Style(color="grey35"),
        tool_name=Style(color="deep_sky_blue1", bold=True),
        tool_output=Style(color="grey74"),
        code_bg=Style(bgcolor="grey15", color="grey84"),
        prompt_symbol="\u276f",
        prompt_color=Style(color="bright_blue", bold=True),
    ),
    "minimal": Theme(
        name="minimal",
        primary=Style(color="white", bold=True),
        secondary=Style(color="bright_white"),
        accent=Style(color="bright_cyan"),
        error=Style(color="red", bold=True),
        warning=Style(color="yellow"),
        success=Style(color="green", bold=True),
        muted=Style(color="grey50"),
        bg=Style(),
        fg=Style(color="white"),
        border=Style(color="grey50"),
        tool_name=Style(color="bright_cyan", bold=True),
        tool_output=Style(color="white"),
        code_bg=Style(bgcolor="grey11", color="white"),
        prompt_symbol=">",
        prompt_color=Style(color="white", bold=True),
    ),
}
