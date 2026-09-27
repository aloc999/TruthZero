import asyncio

from truthzero.swarm import Blackboard, SwarmScheduler
from truthzero.scoring import cvss31_score, JevFilter, AdaptiveScorer
from truthzero import playbooks as pb


def test_blackboard_pheromone_decay():
    b = Blackboard()
    fid = b.add("SESSION", "sess", target="t")
    f = b.get(fid)
    assert f.decayed_weight() > 0.9
    f.created_at -= 3600  # 1h later, 15min half-life → ~0.06
    assert f.decayed_weight() < 0.2
    assert b.hot() == []  # stale, no hot findings


def test_blackboard_reinforce():
    b = Blackboard()
    fid = b.add("VULN", "x", target="t")
    f = b.get(fid)
    f.weight = 0.5
    f.reinforce(0.4)
    assert abs(f.weight - 0.9) < 1e-6


def test_cvss_vectors():
    score, sev = cvss31_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H")
    assert score == 10.0 and sev == "critical"
    score2, sev2 = cvss31_score("garbage")
    assert (score2, sev2) == (0.0, "none")


def test_jev_fails_open():
    j = JevFilter(enabled=False)
    v = j.verify("xss maybe", "", "")
    assert v.keep is True
    j2 = JevFilter(enabled=True)
    v2 = j2.verify("XSS", "poc curl proof", "HTTP/1.1 200 response with request")
    assert v2.keep and v2.confidence >= 0.8
    v3 = j2.verify("thing", "may be possibly theoretical unable to confirm", "")
    assert v3.keep is False  # likely FP with zero evidence


def test_adaptive_ranking():
    b = Blackboard()
    b.add("OBJECT_REF", "ref", target="t")
    b.add("ENDPOINT", "ep", target="t")
    s = AdaptiveScorer()
    ranked = [p.name for p in s.top(b, 3)]
    assert "bola-idor-chain" in ranked  # hot OBJECT_REF+ENDPOINT → top-3
    s.reinforce("xss-chain")
    assert s._wins["xss-chain"] == 1


def test_swarm_run_headless():
    async def go():
        b = Blackboard()
        sched = SwarmScheduler(b, max_rounds=3,
                               scope_checker=lambda t: True)

        async def runner(spec, tgt, board):
            if spec.name == "recon":
                board.add("VULN", "cand", target=tgt)
                return "CANDIDATE: x"
            if spec.name == "exploit":
                board.add("VULN_CONFIRMED", "proven", target=tgt,
                          evidence="resp")
                return "CONFIRMED: proven"
            return ""
        res = await sched.run("example.com", runner)
        assert res.rounds >= 1
        assert res.findings_total >= 2
        return res
    res = asyncio.run(go())
    assert res.stopped_reason == "completed"


def test_swarm_scope_block():
    async def go():
        b = Blackboard()
        sched = SwarmScheduler(b, max_rounds=3,
                               scope_checker=lambda t: False)
        res = await sched.run("evil.com", lambda *a: asyncio.sleep(0, result=""))
        assert "out of scope" in res.stopped_reason
    asyncio.run(go())


def test_playbooks_chains_load():
    assert "bug-bounty" in pb.list_playbooks()
    assert len(pb.list_playbooks()) == 5
    data = pb.load_playbook("bug-bounty")
    assert data.get("name") == "bug-bounty" and len(data.get("steps", [])) >= 5
    assert "bola-idor-chain" in pb.list_chains()
    chain = pb.load_chain("ssrf-to-rce")
    assert chain.get("severity") == "critical"


def test_scope_enforcement_in_agent():
    from truthzero.agent import TruthCoreAgent
    from truthzero.config import TruthZeroConfig
    from truthzero.scope import ScopeManager
    import json
    cfg = TruthZeroConfig(provider="ollama", model="x")
    agent = TruthCoreAgent(cfg)
    sm = ScopeManager()
    sm.add_in_scope("allowed.com")
    agent._scope = sm
    reason = agent._scope_check_tool(
        "port_scan", {"target": "evil.com"}, sm)
    assert "OUT OF SCOPE" in reason
    ok = agent._scope_check_tool("port_scan", {"target": "allowed.com"}, sm)
    assert ok == ""
    ok2 = agent._scope_check_tool("read_file", {"file_path": "/etc/passwd"}, sm)
    assert ok2 == ""  # non-network tools skip


def test_sarif_export():
    from truthzero.reports import ReportGenerator
    g = ReportGenerator()
    msgs = [{"role": "assistant",
             "content": "Found critical SQL injection vulnerability with poc curl proof"}]
    sarif = g.to_sarif(msgs)
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"][0]["results"]) >= 1
