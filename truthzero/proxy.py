import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProxyConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 8080
    protocol: str = "http"
    ssl_verify: bool = False
    exclude_hosts: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.exclude_hosts:
            self.exclude_hosts = ["api.openai.com", "api.anthropic.com", "api.deepseek.com"]

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def httpx_proxy(self) -> Optional[str]:
        if not self.enabled:
            return None
        return self.url

    def should_proxy(self, target_url: str) -> bool:
        if not self.enabled:
            return False
        for host in self.exclude_hosts:
            if host in target_url:
                return False
        return True

    def get_httpx_kwargs(self, target_url: str = "") -> dict:
        kwargs = {}
        if self.should_proxy(target_url):
            kwargs["proxy"] = self.url
        if not self.ssl_verify:
            kwargs["verify"] = False
        return kwargs


class ProxyManager:
    def __init__(self, config: ProxyConfig = None):
        self.config = config or ProxyConfig()

    def enable(self, host: str = "127.0.0.1", port: int = 8080):
        self.config.enabled = True
        self.config.host = host
        self.config.port = port

    def disable(self):
        self.config.enabled = False

    @property
    def is_active(self) -> bool:
        return self.config.enabled

    def status(self) -> dict:
        return {
            "enabled": self.config.enabled,
            "proxy_url": self.config.url if self.config.enabled else None,
            "ssl_verify": self.config.ssl_verify,
            "excluded": self.config.exclude_hosts,
        }

    async def test_connection(self) -> tuple[bool, str]:
        import httpx
        try:
            async with httpx.AsyncClient(proxy=self.config.url, timeout=5.0, verify=False) as client:
                resp = await client.get("http://httpbin.org/ip")
                if resp.status_code == 200:
                    return True, f"Proxy active at {self.config.url}"
                return False, f"Proxy returned status {resp.status_code}"
        except Exception as e:
            return False, f"Proxy connection failed: {e}"

    @classmethod
    def from_env(cls) -> "ProxyManager":
        config = ProxyConfig()
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy_url:
            config.enabled = True
            if "://" in proxy_url:
                config.protocol, rest = proxy_url.split("://", 1)
            else:
                rest = proxy_url
            if ":" in rest:
                config.host, port_str = rest.rsplit(":", 1)
                try:
                    config.port = int(port_str.rstrip("/"))
                except ValueError:
                    config.port = 8080
            else:
                config.host = rest.rstrip("/")
        return cls(config)
