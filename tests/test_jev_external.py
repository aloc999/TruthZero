import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from truthzero.scoring import JevFilter
from truthzero.scoring.jev_external import ExternalJevBackend


class _StubHandler(BaseHTTPRequestHandler):
    prob = 0.9
    code = 200

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0) or 0)
        self.rfile.read(length)
        body = json.dumps({"answers": [{"id": "supported",
                                        "probability": type(self).prob}],
                           "usage": {}}).encode()
        self.send_response(type(self).code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _stub_server(prob=0.9, code=200):
    _StubHandler.prob = prob
    _StubHandler.code = code
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_external_keep_and_drop():
    srv = _stub_server(prob=0.85)
    try:
        be = ExternalJevBackend(api_key="k", base_url="http://127.0.0.1:%d" % srv.server_address[1])
        assert be.available()
        v = be.verify("SQLi", "detail", "poc curl proof")
        assert v is not None and v.keep and v.probability == 0.85
    finally:
        srv.shutdown()
    srv = _stub_server(prob=0.2)
    try:
        be = ExternalJevBackend(api_key="k", base_url="http://127.0.0.1:%d" % srv.server_address[1])
        v = be.verify("maybe", "hedge", "")
        assert v is not None and not v.keep
    finally:
        srv.shutdown()


def test_external_abstains():
    # abstain zone
    srv = _stub_server(prob=0.5)
    try:
        be = ExternalJevBackend(api_key="k", base_url="http://127.0.0.1:%d" % srv.server_address[1])
        assert be.verify("x", "", "") is None
    finally:
        srv.shutdown()
    # server error → abstain
    srv = _stub_server(prob=0.1, code=500)
    try:
        be = ExternalJevBackend(api_key="k", base_url="http://127.0.0.1:%d" % srv.server_address[1])
        assert be.verify("x", "", "") is None
    finally:
        srv.shutdown()
    # no key → unavailable
    be = ExternalJevBackend(api_key="", base_url="http://127.0.0.1:1")
    assert not be.available()
    assert be.verify("x", "", "") is None
    # unreachable → abstain (fail open)
    be = ExternalJevBackend(api_key="k", base_url="http://127.0.0.1:1", timeout=2)
    assert be.verify("x", "", "") is None


class _FakeBackend:
    def __init__(self, verdict):
        self._verdict = verdict

    def verify(self, title, detail="", evidence=""):
        return self._verdict


def test_and_gate():
    from truthzero.scoring.jev_external import ExternalVerdict
    hedge = ("may be possibly theoretical unable to confirm", "", "high")
    # both drop → drop
    j = JevFilter(enabled=True, _external=_FakeBackend(ExternalVerdict(False, 0.2, {})))
    v = j.verify("t", *hedge)
    assert v.keep is False and "agrees" in v.reason
    # builtin drops, external keeps → keep for human review
    j = JevFilter(enabled=True, _external=_FakeBackend(ExternalVerdict(True, 0.8, {})))
    v = j.verify("t", *hedge)
    assert v.keep is True and "human review" in v.reason
    # external abstains → keep for human review
    j = JevFilter(enabled=True, _external=_FakeBackend(None))
    v = j.verify("t", *hedge)
    assert v.keep is True
    # low severity → external skipped, builtin verdict stands
    j = JevFilter(enabled=True, _external=_FakeBackend(ExternalVerdict(False, 0.1, {})))
    v = j.verify("t", "may be possibly theoretical unable to confirm", "", "low")
    assert v.keep is False and "skipped" in v.reason
    # backend=builtin never consults
    j = JevFilter(enabled=True, backend="builtin",
                  _external=_FakeBackend(ExternalVerdict(False, 0.1, {})))
    v = j.verify("t", *hedge)
    assert "skipped" in v.reason
