import pytest

textual = pytest.importorskip("textual")  # noqa: E402 - gate before heavy imports

from truthzero.tui_app import (  # noqa: E402 - after importorskip gate
    TUI_PALETTES,
    TruthZeroTUI,
    _st,
    build_tui_css,
    tui_palette,
)


def test_palettes():
    assert set(TUI_PALETTES) == {"hacker", "cyberpunk", "dark", "minimal"}
    assert tui_palette("cyberpunk")["primary"] == "#ff2a6d"
    assert tui_palette("hacker")["primary"] == "#00ff41"
    assert tui_palette("nope")["primary"] == "#00ff41"  # fallback
    assert tui_palette(None)["primary"] == "#00ff41"
    for name, pal in TUI_PALETTES.items():
        assert set(pal) == {"primary", "accent", "hot", "warn", "err",
                            "persona", "bg", "surface", "edge"}, name


def test_css_build():
    css = build_tui_css(TruthZeroTUI._CSS_TEMPLATE, tui_palette("cyberpunk"))
    assert "#ff2a6d" in css
    assert "$primary" not in css and "$bg" not in css
    css_h = build_tui_css(TruthZeroTUI._CSS_TEMPLATE, tui_palette("hacker"))
    assert "#00ff41" in css_h


def test_st_helper():
    pal = tui_palette("cyberpunk")
    assert _st(pal, "primary") == "bold #ff2a6d"
    assert _st(pal, "accent", bold=False) == "#00f0ff"
    assert _st(pal, "warn", pre="dim ") == "dim bold #ffd319"


def test_app_takes_theme():
    from types import SimpleNamespace
    app = TruthZeroTUI(agent=None, config=SimpleNamespace(theme="cyberpunk"))
    assert app._tui_pal["primary"] == "#ff2a6d"
    app2 = TruthZeroTUI(agent=None, config=SimpleNamespace(theme="hacker"))
    assert app2._tui_pal["primary"] == "#00ff41"
    app3 = TruthZeroTUI(agent=None, config=None)
    assert app3._tui_pal["primary"] == "#00ff41"
