import asyncio
import json
import subprocess
import sys

from zer0code.asm import ASMSnapshot, CIGate
from zer0code.scoring import cvss31_score


def test_asm_diff(tmp_path):
    old = ASMSnapshot(target="t", subdomains=["a.t", "b.t"], hosts=["1.1.1.1"],
                      endpoints=["/"], ports=["80"])
    new = ASMSnapshot(target="t", subdomains=["a.t", "c.t"], hosts=["1.1.1.1"],
                      endpoints=["/", "/api"], ports=["80", "443"])
    p1, p2 = str(tmp_path / "o.json"), str(tmp_path / "n.json")
    old.save(p1)
    new.save(p2)
    d = ASMSnapshot.load(p2).diff(ASMSnapshot.load(p1))
    assert d["subdomains"]["added"] == ["c.t"]
    assert d["subdomains"]["removed"] == ["b.t"]
    assert "+ c.t" in ASMSnapshot().format_diff(d)


def test_ci_gate():
    g = CIGate(fail_on=("high", "critical"))
    assert g.evaluate([{"severity": "medium"}])["passed"] is True
    res = g.evaluate([{"severity": "high", "title": "SQLi"}])
    assert res["passed"] is False and res["exit_code"] == 2
    sarif = {"runs": [{"results": [
        {"level": "error", "message": {"text": "RCE"}},
        {"level": "note", "message": {"text": "info"}}]}]}
    assert g.evaluate_sarif(sarif)["blocking"] == 1


def test_adapters_registered():
    from zer0code.tools import ALL_TOOLS
    names = [t.name for t in ALL_TOOLS]
    assert "sqlmap_scan" in names
    assert "msf_run" in names
    assert "zap_scan" in names
    assert "burp_bridge" in names


def test_adapters_fail_safe():
    """Missing binaries / destructive flags fail with clear errors, no crash."""
    from zer0code.tools.sqlmap_tool import SqlmapTool
    from zer0code.tools.metasploit_tool import MetasploitTool
    from zer0code.tools.zap_tool import ZapTool

    async def go():
        r1 = await SqlmapTool().execute(
            url="http://example.com/?id=1", extra_args="--os-shell")
        assert r1.success is False and "Blocked" in (r1.error or "")
        r2 = await MetasploitTool().execute(
            module="exploit/windows/smb/ms17_010_eternalblue", rhosts="1.2.3.4")
        assert r2.success is False and "allowlist" in (r2.error or "")
        r3 = await ZapTool().execute(target="", mode="baseline")
        assert r3.success is False
        return True
    assert asyncio.run(go()) is True


def test_burp_bridge_offline():
    from zer0code.tools.burp_bridge import BurpBridgeTool
    async def go():
        r = await BurpBridgeTool().execute(
            action="status", base_url="http://127.0.0.1:19999")
        assert r.success is False
        assert "not reachable" in (r.error or "")
    asyncio.run(go())


def test_mcp_server_stdio():
    """initialize → tools/list → tools/call over stdio."""
    reqs = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "cvss_score",
                               "arguments": {"vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H"}}}),
        json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": "playbook_list", "arguments": {}}}),
    ]) + "\n"
    p = subprocess.run([sys.executable, "-m", "zer0code.mcp_run"],
                       input=reqs, capture_output=True, text=True, timeout=30)
    lines = [json.loads(ln) for ln in p.stdout.strip().splitlines() if ln.strip()]
    by_id = {ln.get("id"): ln for ln in lines}
    assert by_id[1]["result"]["serverInfo"]["name"] == "zer0code"
    assert any(t["name"] == "blackboard_write" for t in by_id[2]["result"]["tools"])
    assert "10.0" in by_id[3]["result"]["content"][0]["text"]
    assert "bug-bounty" in by_id[4]["result"]["content"][0]["text"]


def test_pgboard_fails_open():
    """No Postgres here → connect() False, memory board unaffected."""
    from zer0code.swarm import PostgresBoard
    b = PostgresBoard("postgresql://u:p@127.0.0.1:19999/db")
    assert b.connect() is False
    assert b.error != ""
