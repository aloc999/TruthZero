"""Slash-command audit: every suggested command must do something sane, never crash."""
import pytest

textual = pytest.importorskip("textual")  # noqa: E402 - gate before heavy imports

from truthzero.tui_app import TruthZeroTUI  # noqa: E402 - after importorskip gate


class FakeConv:
    def __init__(self):
        self.lines = []

    def write(self, renderable):
        try:
            self.lines.append(renderable.plain)
        except Exception:
            self.lines.append(str(renderable))

    def clear(self):
        self.lines.append("<clear>")

    @property
    def text(self):
        return "\n".join(self.lines)


def _app():
    from types import SimpleNamespace
    cfg = SimpleNamespace(provider="openai", model="gpt-4o", theme="hacker",
                          memory_enabled=False)
    return TruthZeroTUI(agent=None, config=cfg)


@pytest.mark.asyncio
async def test_template_list_and_unknown():
    app, conv = _app(), FakeConv()
    await app._handle_slash("/template", conv)
    assert "Usage: /template" in conv.text
    conv2 = FakeConv()
    await app._handle_slash("/template nope-not-real", conv2)
    assert "not found" in conv2.text


@pytest.mark.asyncio
async def test_session_no_agent():
    app, conv = _app(), FakeConv()
    await app._handle_slash("/session list", conv)
    assert "unavailable" in conv.text


@pytest.mark.asyncio
async def test_branch_no_agent_silent():
    app, conv = _app(), FakeConv()
    await app._handle_slash("/branch wat", conv)
    assert conv.text == ""  # no agent → no output, no crash


@pytest.mark.asyncio
async def test_scan_lab_bench(tmp_path, monkeypatch):
    import truthzero.headless as h
    monkeypatch.setattr(h, "BOARDS_DIR", tmp_path)
    app, conv = _app(), FakeConv()
    await app._handle_slash("/scan example.com --scope example.com --rounds 1", conv)
    assert "Done:" in conv.text and "Board:" in conv.text
    conv2 = FakeConv()
    await app._handle_slash("/scan", conv2)
    assert "Usage: /scan" in conv2.text
    conv3 = FakeConv()
    await app._handle_slash("/scan evil.com --scope example.com", conv3)
    assert "out of scope" in conv3.text.lower()
    conv4 = FakeConv()
    await app._handle_slash("/lab list", conv4)
    assert "crapi" in conv4.text
    conv5 = FakeConv()
    await app._handle_slash("/lab", conv5)
    assert "crapi" in conv5.text
    conv6 = FakeConv()
    await app._handle_slash("/bench", conv6)
    assert "Bench score:" in conv6.text
    conv7 = FakeConv()
    await app._handle_slash("/bench --suite mini", conv7)
    assert "Mini-suite:" in conv7.text


@pytest.mark.asyncio
async def test_help_and_unknown():
    app, conv = _app(), FakeConv()
    await app._handle_slash("/help", conv)
    assert "/template" in conv.text and "/session" in conv.text
    conv2 = FakeConv()
    await app._handle_slash("/boguscmd", conv2)
    assert "Unknown" in conv2.text


@pytest.mark.asyncio
async def test_compact_no_agent():
    app, conv = _app(), FakeConv()
    await app._handle_slash("/compact", conv)
    assert "Nothing to compact" in conv.text


@pytest.mark.asyncio
async def test_provider_invalid_lists_all():
    app, conv = _app(), FakeConv()
    await app._handle_slash("/provider nope", conv)
    for p in ("together", "gemini", "lmstudio", "orcarouter"):
        assert p in conv.text


@pytest.mark.asyncio
async def test_mounted_theme_and_provider():
    """Mounted paths: /theme cycles live, /provider valid switches."""
    from types import SimpleNamespace

    from truthzero.tui_app import build_tui_css, tui_palette

    class Cfg(SimpleNamespace):
        def save(self):
            self.saved = True

    cfg = Cfg(provider="openai", model="m", theme="hacker", memory_enabled=False)
    pal = tui_palette("hacker")
    TruthZeroTUI.CSS = build_tui_css(TruthZeroTUI._CSS_TEMPLATE, pal)
    app = TruthZeroTUI(agent=None, config=cfg)
    async with app.run_test(size=(100, 30)) as pilot:
        for cmd in ["/theme cyberpunk", "/provider together"]:
            for ch in cmd:
                await pilot.press(ch)
            await pilot.press("enter")
            await pilot.pause(0.4)
    assert cfg.theme == "cyberpunk"
    assert getattr(cfg, "saved", False) is True
    assert cfg.provider == "together"
    assert app._tui_pal["primary"] == "#ff2a6d"


@pytest.mark.asyncio
async def test_model_picker_select_and_cancel():
    from types import SimpleNamespace

    from truthzero.tui_app import (
        PickerScreen,
        build_tui_css,
        tui_palette,
    )

    class Cfg(SimpleNamespace):
        def save(self):
            self.saved = True

    cfg = Cfg(provider="openai", model="gpt-4o", theme="cyberpunk",
              memory_enabled=False)
    TruthZeroTUI.CSS = build_tui_css(TruthZeroTUI._CSS_TEMPLATE,
                                    tui_palette("cyberpunk"))
    app = TruthZeroTUI(agent=None, config=cfg)
    async with app.run_test(size=(100, 32)) as pilot:
        for ch in "/model":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause(0.6)
        assert isinstance(app.screen, PickerScreen)
        await pilot.press("down", "down", "enter")
        await pilot.pause(0.5)
        assert cfg.model == "gpt-4-turbo"
        assert cfg.saved is True
        for ch in "/provider":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause(0.6)
        assert isinstance(app.screen, PickerScreen)
        await pilot.press("escape")
        await pilot.pause(0.4)
        assert cfg.provider == "openai"  # cancel keeps value
        await pilot.press("ctrl+o")
        await pilot.pause(0.5)
        assert isinstance(app.screen, PickerScreen)
        await pilot.press("escape")
        ib = app.query_one("#input-box")
        assert ib.outer_size.height == 3  # compact chat box


@pytest.mark.asyncio
async def test_scan_out_of_scope_clean():
    app = _app()
    conv = FakeConv()
    await app._handle_slash("/scan evil.com --scope example.com", conv)
    assert "OUT OF SCOPE" in conv.text
    assert "Hunting" not in conv.text


@pytest.mark.asyncio
async def test_escape_closes_panel_and_refocuses():
    from types import SimpleNamespace

    from truthzero.tui_app import build_tui_css, tui_palette

    cfg = SimpleNamespace(provider="openai", model="m", theme="hacker",
                          memory_enabled=False)
    TruthZeroTUI.CSS = build_tui_css(TruthZeroTUI._CSS_TEMPLATE,
                                    tui_palette("hacker"))
    app = TruthZeroTUI(agent=None, config=cfg)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("ctrl+b")  # open side panel
        await pilot.pause(0.3)
        assert app.show_panel is True
        await pilot.press("escape")  # ESC closes panel
        await pilot.pause(0.3)
        assert app.show_panel is False
        # main chrome still visible after ESC
        assert app.query_one("#welcome").display is not False
        assert app.query_one("#header-bar").display is not False
        assert app.query_one("#main-area").display is not False


@pytest.mark.asyncio
async def test_rerun_and_telemetry(tmp_path, monkeypatch):
    import truthzero.headless as h
    monkeypatch.setattr(h, "BOARDS_DIR", tmp_path)
    from types import SimpleNamespace

    from textual.widgets import RichLog

    from truthzero.tui_app import build_tui_css, tui_palette

    cfg = SimpleNamespace(provider="openai", model="m", theme="hacker",
                          memory_enabled=False)
    TruthZeroTUI.CSS = build_tui_css(TruthZeroTUI._CSS_TEMPLATE,
                                    tui_palette("hacker"))
    app = TruthZeroTUI(agent=None, config=cfg)
    async with app.run_test(size=(110, 34)) as pilot:
        for ch in "/scan example.com --scope example.com --rounds 1":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause(1.5)
        assert app._last_scan_cmd.startswith("/scan")
        assert app._last_board_file != ""
        assert app.show_panel is True
        # ctrl+r re-runs identical scan
        await pilot.press("ctrl+r")
        await pilot.pause(1.5)
        conv = app.query_one("#conversation", RichLog)
        assert conv._line_cache, "expected conversation content"


@pytest.mark.asyncio
async def test_welcome_buttons_and_hide():
    from types import SimpleNamespace

    from textual.widgets import Input

    from truthzero.tui_app import build_tui_css, tui_palette

    cfg = SimpleNamespace(provider="openai", model="m", theme="hacker",
                          memory_enabled=False)
    TruthZeroTUI.CSS = build_tui_css(TruthZeroTUI._CSS_TEMPLATE,
                                    tui_palette("hacker"))
    app = TruthZeroTUI(agent=None, config=cfg)
    async with app.run_test(size=(110, 32)) as pilot:
        await pilot.pause(0.5)
        welcome = app.query_one("#welcome")
        assert welcome.display is not False
        assert len(app.query("#welcome-actions Button")) == 4
        await pilot.click("#btn-lab")
        await pilot.pause(0.4)
        assert app.query_one("#user-input", Input).value == "/lab "
        await pilot.click("#btn-bench")
        await pilot.pause(0.4)
        assert "bench" in app.query_one("#user-input", Input).value
        await pilot.press("enter")  # submit hides welcome
        await pilot.pause(0.6)
        assert welcome.display is False
