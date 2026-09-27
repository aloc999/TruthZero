import asyncio
import json
import os
from typing import Optional

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading
    HAS_HTTP = True
except ImportError:
    HAS_HTTP = False


class ZeroCoreAPIHandler(BaseHTTPRequestHandler):
    agent = None

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            prompt = data.get("prompt", data.get("message", ""))
            if not prompt:
                self.send_error(400, "Missing 'prompt' field")
                return

            if self.agent:
                loop = asyncio.new_event_loop()
                try:
                    response = loop.run_until_complete(self.agent.run(prompt))
                finally:
                    loop.close()
            else:
                response = "Agent not initialized"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "response": response,
                "tokens": self.agent.total_tokens if self.agent else 0,
                "cost": self.agent.total_cost if self.agent else "$0",
            }).encode())

        elif self.path == "/api/tools":
            tools = []
            if self.agent:
                for name, tool in self.agent.tool_registry.items():
                    tools.append({"name": name, "description": getattr(tool, "description", "")})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"tools": tools}).encode())

        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "agent": self.agent is not None}).encode())

        elif self.path == "/api/status":
            status = {
                "model": self.agent.config.model if self.agent else "",
                "provider": self.agent.config.provider if self.agent else "",
                "tokens": self.agent.total_tokens if self.agent else 0,
                "cost": self.agent.total_cost if self.agent else "$0",
                "messages": self.agent.message_count if self.agent else 0,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())

        else:
            self.send_error(404)


class APIServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 3117):
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self, agent=None):
        ZeroCoreAPIHandler.agent = agent
        self._server = HTTPServer((self.host, self.port), ZeroCoreAPIHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://{self.host}:{self.port}"

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
