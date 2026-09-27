import asyncio
import http.client
import json
import urllib.parse

from truthzero.dashboard import DashboardServer
from truthzero.headless import run_headless_scan


def _post(port, path, data):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    body = json.dumps(data)
    conn.request("POST", path, body, {"Content-Type": "application/json"})
    resp = conn.getresponse()
    out = (resp.status, json.loads(resp.read().decode() or "{}"))
    conn.close()
    return out


def _get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    conn.request("GET", path)
    resp = conn.getresponse()
    out = (resp.status, resp.read().decode())
    conn.close()
    return out


def test_headless_scan_and_persist(tmp_path, monkeypatch):
    import truthzero.headless as h
    monkeypatch.setattr(h, "BOARDS_DIR", tmp_path)
    result, board_file = asyncio.run(
        run_headless_scan("example.com", scope="example.com", rounds=2))
    assert result.findings_total >= 3
    assert board_file.endswith(".json")
    assert tmp_path.joinpath(board_file.split("/")[-1]).exists()


def test_headless_scope_block():
    import pytest
    with pytest.raises(PermissionError):
        asyncio.run(run_headless_scan("evil.com", scope="example.com", rounds=1))


def test_headless_sequential_and_jev():
    result, _ = asyncio.run(
        run_headless_scan("example.com", scope="example.com",
                          mode="sequential", persist=False))
    assert result.stopped_reason == "sequential"
    assert result.rounds == 1
    assert result.findings_total >= 3
    # jev sweep keeps evidenced demo findings (fail open by design)
    result2, _ = asyncio.run(
        run_headless_scan("example.com", scope="example.com", rounds=1,
                          jev=True, persist=False))
    assert result2.findings_total >= 3
    assert "+jev(" in result2.stopped_reason


def test_headless_on_event():
    calls = []
    result, _ = asyncio.run(
        run_headless_scan("example.com", scope="example.com", rounds=2,
                          persist=False,
                          on_event=lambda rno, fired, board: calls.append(
                              (rno, sorted(fired), len(board.all())))))
    assert len(calls) == result.rounds == 2
    assert all(n >= 0 for _, _, n in calls)
    # sequential fires once too
    calls2 = []
    asyncio.run(run_headless_scan("example.com", scope="example.com",
                                  mode="sequential", persist=False,
                                  on_event=lambda rno, fired, board: calls2.append(rno)))
    assert calls2 == [0]


def test_scan_strict_exit_code():
    from click.testing import CliRunner
    from truthzero.cli import cli
    r = CliRunner().invoke(
        cli, ["scan", "evil.com", "--scope", "example.com", "--strict"])
    assert r.exit_code == 1
    r = CliRunner().invoke(cli, ["scan", "evil.com", "--scope", "example.com"])
    assert r.exit_code == 0
    r = CliRunner().invoke(
        cli, ["scan", "example.com", "--scope", "example.com",
              "--no-swarm", "--rounds", "1"])
    assert r.exit_code == 0 and "[sequential]" in r.output


def test_dashboard_api():
    srv = DashboardServer(0)
    url = srv.start_background()
    port = int(urllib.parse.urlparse(url).port)
    try:
        # scan (in scope)
        code, res = _post(port, "/api/scan",
                          {"target": "example.com", "scope": "example.com",
                           "rounds": 2})
        assert code == 200, res
        assert res["findings_total"] >= 3
        board_file = res["board_file"]
        assert board_file

        # findings for that board
        code, body = _get(port, "/api/findings?board_file=" +
                          urllib.parse.quote(board_file))
        assert code == 200
        data = json.loads(body)
        assert data["summary"]["total"] >= 3

        # sarif
        code, body = _get(port, "/api/sarif?board_file=" +
                          urllib.parse.quote(board_file))
        assert code == 200
        assert json.loads(body)["version"] == "2.1.0"

        # out of scope → 403 fail closed
        code, res = _post(port, "/api/scan",
                          {"target": "evil.com", "scope": "example.com"})
        assert code == 403

        # missing target → 400
        code, _ = _post(port, "/api/scan", {})
        assert code == 400

        # index
        code, body = _get(port, "/")
        assert code == 200 and ("TRUTHZERO" in body or "swarm" in body.lower())
        assert "topology" in body.lower() or "topo" in body
        assert "cyberpunk" in body.lower() or "00f0ff" in body

        # unknown → 404
        code, _ = _get(port, "/nope")
        assert code == 404
    finally:
        srv.stop()
