import asyncio
import os
import shutil
import subprocess
import sys
from typing import Optional


class NotificationManager:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._method = self._detect_method()

    def _detect_method(self) -> Optional[str]:
        if sys.platform == "darwin":
            return "osascript"
        if sys.platform == "linux":
            if shutil.which("notify-send"):
                return "notify-send"
            if shutil.which("zenity"):
                return "zenity"
        if sys.platform == "win32":
            return "win-toast"
        return "bell"

    def notify(self, title: str, message: str, sound: bool = True):
        if not self.enabled:
            return

        try:
            if self._method == "osascript":
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "{message}" with title "{title}" sound name "Glass"'
                ], capture_output=True, timeout=5)

            elif self._method == "notify-send":
                cmd = ["notify-send", title, message, "--icon=dialog-information"]
                subprocess.run(cmd, capture_output=True, timeout=5)

            elif self._method == "zenity":
                subprocess.run([
                    "zenity", "--notification", f"--text={title}: {message}"
                ], capture_output=True, timeout=5)

            elif self._method == "win-toast":
                try:
                    from ctypes import windll
                    windll.user32.MessageBoxW(0, message, title, 0x40)
                except Exception:
                    pass

            if sound and self._method != "osascript":
                print("\a", end="", flush=True)

        except Exception:
            if sound:
                print("\a", end="", flush=True)

    async def notify_async(self, title: str, message: str, sound: bool = True):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.notify, title, message, sound)

    def task_complete(self, task_name: str, duration_secs: float = 0):
        dur = f" ({duration_secs:.1f}s)" if duration_secs else ""
        self.notify("ZER0CODE", f"Task complete: {task_name}{dur}")

    def error(self, message: str):
        self.notify("ZER0CODE Error", message, sound=True)

    @property
    def available(self) -> bool:
        return self._method is not None
