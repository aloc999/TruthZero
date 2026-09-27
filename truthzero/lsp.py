import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Optional


LANG_SERVERS = {
    ".py": ("pylsp", []),
    ".js": ("typescript-language-server", ["--stdio"]),
    ".ts": ("typescript-language-server", ["--stdio"]),
    ".jsx": ("typescript-language-server", ["--stdio"]),
    ".tsx": ("typescript-language-server", ["--stdio"]),
    ".go": ("gopls", ["serve"]),
    ".rs": ("rust-analyzer", []),
    ".java": ("jdtls", []),
}


class LSPClient:
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._responses: dict[int, dict] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False

    @staticmethod
    def detect_server(filepath: str) -> Optional[tuple[str, list[str]]]:
        ext = Path(filepath).suffix.lower()
        return LANG_SERVERS.get(ext)

    def connect(self, cmd: str, args: Optional[list[str]] = None):
        full_cmd = [cmd] + (args or [])
        self._process = subprocess.Popen(
            full_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        self._send_request("initialize", {
            "processId": os.getpid(),
            "capabilities": {},
            "rootUri": f"file://{os.getcwd()}",
        })

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send_request(self, method: str, params: dict) -> int:
        req_id = self._next_id()
        message = json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        })
        content = f"Content-Length: {len(message)}\r\n\r\n{message}"
        if self._process and self._process.stdin:
            self._process.stdin.write(content.encode())
            self._process.stdin.flush()
        return req_id

    def _send_notification(self, method: str, params: dict):
        message = json.dumps({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        })
        content = f"Content-Length: {len(message)}\r\n\r\n{message}"
        if self._process and self._process.stdin:
            self._process.stdin.write(content.encode())
            self._process.stdin.flush()

    def _read_loop(self):
        while self._running and self._process and self._process.stdout:
            try:
                header = b""
                while not header.endswith(b"\r\n\r\n"):
                    byte = self._process.stdout.read(1)
                    if not byte:
                        self._running = False
                        return
                    header += byte
                length = 0
                for line in header.decode().split("\r\n"):
                    if line.startswith("Content-Length:"):
                        length = int(line.split(":")[1].strip())
                if length > 0:
                    body = self._process.stdout.read(length)
                    msg = json.loads(body)
                    if "id" in msg:
                        self._responses[msg["id"]] = msg
            except Exception:
                break

    def _wait_response(self, req_id: int, timeout: float = 10.0) -> Optional[dict]:
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if req_id in self._responses:
                return self._responses.pop(req_id)
            time.sleep(0.05)
        return None

    def open_file(self, path: str):
        path = os.path.abspath(path)
        ext = Path(path).suffix.lower()
        lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go", ".rs": "rust", ".java": "java"}
        lang = lang_map.get(ext, "plaintext")
        with open(path) as f:
            text = f.read()
        self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": f"file://{path}",
                "languageId": lang,
                "version": 1,
                "text": text,
            },
        })

    def get_diagnostics(self, path: str) -> list[dict]:
        path = os.path.abspath(path)
        req_id = self._send_request("textDocument/diagnostic", {
            "textDocument": {"uri": f"file://{path}"},
        })
        resp = self._wait_response(req_id)
        if not resp or "result" not in resp:
            return []
        items = resp["result"].get("items", resp["result"].get("diagnostics", []))
        results = []
        severity_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        for item in items:
            rng = item.get("range", {}).get("start", {})
            results.append({
                "file": path,
                "line": rng.get("line", 0) + 1,
                "column": rng.get("character", 0) + 1,
                "severity": severity_map.get(item.get("severity", 3), "info"),
                "message": item.get("message", ""),
                "source": item.get("source", ""),
            })
        return results

    def close(self):
        self._running = False
        if self._process:
            self._send_request("shutdown", {})
            self._send_notification("exit", {})
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                if self._process:
                    self._process.kill()
            self._process = None
