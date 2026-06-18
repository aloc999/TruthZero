import base64
import hashlib
import json
import os
import platform
import warnings
from typing import Optional

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class CredentialManager:
    def __init__(self, store_path: str = "~/.zer0code/credentials.enc"):
        self.store_path = os.path.expanduser(store_path)
        if not HAS_CRYPTO:
            warnings.warn(
                "cryptography library not installed, falling back to base64 obfuscation. "
                "Install with: pip install cryptography",
                stacklevel=2,
            )

    def _get_key(self) -> bytes:
        env_key = os.environ.get("ZER0CODE_KEY")
        if env_key:
            key_bytes = hashlib.sha256(env_key.encode()).digest()
        else:
            identity = f"{platform.node()}:{os.getenv('USER', os.getenv('USERNAME', 'zer0code'))}"
            key_bytes = hashlib.sha256(identity.encode()).digest()
        if HAS_CRYPTO:
            return base64.urlsafe_b64encode(key_bytes)
        return key_bytes

    def set(self, name: str, value: str):
        data = self._load()
        data[name] = value
        self._save(data)

    def get(self, name: str) -> Optional[str]:
        data = self._load()
        return data.get(name)

    def delete(self, name: str) -> bool:
        data = self._load()
        if name not in data:
            return False
        del data[name]
        self._save(data)
        return True

    def list_names(self) -> list[str]:
        return list(self._load().keys())

    def has(self, name: str) -> bool:
        return name in self._load()

    def _encrypt(self, data: str) -> str:
        key = self._get_key()
        if HAS_CRYPTO:
            f = Fernet(key)
            return f.encrypt(data.encode()).decode()
        return base64.b64encode(data.encode()).decode()

    def _decrypt(self, data: str) -> str:
        key = self._get_key()
        if HAS_CRYPTO:
            f = Fernet(key)
            return f.decrypt(data.encode()).decode()
        return base64.b64decode(data.encode()).decode()

    def _load(self) -> dict:
        if not os.path.exists(self.store_path):
            return {}
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                encrypted = f.read()
            if not encrypted.strip():
                return {}
            decrypted = self._decrypt(encrypted)
            return json.loads(decrypted)
        except Exception:
            return {}

    def _save(self, data: dict):
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        encrypted = self._encrypt(json.dumps(data))
        with open(self.store_path, "w", encoding="utf-8") as f:
            f.write(encrypted)
