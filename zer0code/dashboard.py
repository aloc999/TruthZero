"""Live dashboard + HTTP API (stdlib only, no deps).

Routes:
  GET  /                        → web/index.html (or inline fallback)
  GET  /api/findings?board_file → {summary, findings[]}
  GET  /api/sarif?board_file    → SARIF 2.1.0
  POST /api/scan                → {target, scope, rounds} → headless swarm,
                                   persists board, fail closed (403 OOS)

Run: `zer0code serve --port 7777`. Ctrl+C stops (cleanup registry owns SIGINT).
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from zer0code.swarm import Blackboard


def _repo_web() -> Path:
    return Path(__file__).resolve().parent.parent / "web" / "index.html"


def _board_from_query(qs: dict) -> Blackboard:
    bf = (qs.get("board_file", [""])[0] or "")
    return Blackboard(bf or None)


def _findings_payload(board: Blackboard) -> dict:
    return {"summary": board.summary(),
            "findings": [f.to_dict() for f in board.all()]}


def _sarif_payload(board: Blackboard) -> dict:
    from zer0code.reports import ReportGenerator
    msgs = [{"role": "assistant",
             "content": f"{f.severity} {f.ftype}: {f.title}\n{f.evidence or f.detail}"}
            for f in board.all()]
    return ReportGenerator().to_sarif(msgs)


class _Handler(BaseHTTPRequestHandler):
    server_version = "ZER0CODE/0.12"

    def _json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, text: str, code: int = 200) -> None:
        body = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                p = _repo_web()
                if p.exists():
                    self._html(p.read_text())
                else:
                    self._html("<h1>ZER0CODE Swarm</h1><p>API: /api/findings /api/sarif, POST /api/scan</p>")
            elif parsed.path == "/api/findings":
                self._json(_findings_payload(_board_from_query(qs)))
            elif parsed.path == "/api/sarif":
                self._json(_sarif_payload(_board_from_query(qs)))
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:
            self._json({"error": str(e)[:300]}, 500)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/scan":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
            data = json.loads(self.rfile.read(length).decode() or "{}")
        except Exception:
            self._json({"error": "invalid JSON"}, 400)
            return
        target = str(data.get("target", "")).strip()
        if not target:
            self._json({"error": "target required"}, 400)
            return
        try:
            from zer0code.headless import run_headless_scan
            result, board_file = asyncio.run(run_headless_scan(
                target, scope=str(data.get("scope", "") or target),
                rounds=int(data.get("rounds", 6) or 6)))
        except PermissionError as e:
            self._json({"error": str(e)}, 403)
            return
        except Exception as e:
            self._json({"error": str(e)[:300]}, 500)
            return
        self._json({"target": result.target, "rounds": result.rounds,
                    "agents_fired": result.agents_fired,
                    "findings_total": result.findings_total,
                    "confirmed": result.confirmed,
                    "duration_s": round(result.duration_s, 1),
                    "board_file": board_file,
                    "stopped_reason": result.stopped_reason})

    def log_message(self, *args) -> None:  # keep test output clean
        pass


class DashboardServer:
    def __init__(self, port: int = 7777):
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        port = self._server.server_address[1] if self._server else self.port
        return f"http://localhost:{port}"

    def start_background(self) -> str:
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        daemon=True)
        self._thread.start()
        return self.url

    def serve_forever(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), _Handler)
        print(f"  Dashboard live at http://localhost:{self._server.server_address[1]} (Ctrl+C to stop)")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._server.server_close()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
