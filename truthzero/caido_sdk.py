from dataclasses import dataclass


@dataclass
class CaidoConfig:
    host: str = "127.0.0.1"
    port: int = 8080
    api_port: int = 48080

    @property
    def api_url(self) -> str:
        return f"http://{self.host}:{self.api_port}"

    @property
    def proxy_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class CaidoSDK:
    def __init__(self, config: CaidoConfig = None):
        self.config = config or CaidoConfig()
        self._connected = False

    async def connect(self) -> tuple[bool, str]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.config.api_url}/graphql",
                    json={"query": "{ __typename }"},
                )
                if resp.status_code == 200:
                    self._connected = True
                    return True, f"Connected to Caido at {self.config.api_url}"
                return False, f"Caido returned status {resp.status_code}"
        except Exception as e:
            return False, f"Cannot connect to Caido: {e}\nMake sure Caido is running on {self.config.api_url}"

    async def _graphql(self, query: str, variables: dict = None) -> dict:
        import httpx
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.config.api_url}/graphql", json=payload)
            return resp.json()

    async def list_requests(self, limit: int = 50, filter_host: str = "", filter_path: str = "", filter_status: int = 0) -> list[dict]:
        query = """
        query GetRequests($first: Int) {
            requests(first: $first, order: { by: ID, ordering: DESC }) {
                edges {
                    node {
                        id
                        host
                        port
                        path
                        query
                        method
                        length
                        response {
                            statusCode
                            length
                        }
                    }
                }
            }
        }
        """
        result = await self._graphql(query, {"first": limit})
        requests = []
        for edge in result.get("data", {}).get("requests", {}).get("edges", []):
            node = edge.get("node", {})
            resp = node.get("response") or {}
            req = {
                "id": node.get("id"),
                "method": node.get("method", "GET"),
                "host": node.get("host", ""),
                "path": node.get("path", ""),
                "query": node.get("query", ""),
                "status": resp.get("statusCode", 0),
                "req_length": node.get("length", 0),
                "resp_length": resp.get("length", 0),
            }
            if filter_host and filter_host.lower() not in req["host"].lower():
                continue
            if filter_path and filter_path.lower() not in req["path"].lower():
                continue
            if filter_status and req["status"] != filter_status:
                continue
            requests.append(req)
        return requests

    async def get_request(self, request_id: str) -> dict:
        query = """
        query GetRequest($id: ID!) {
            request(id: $id) {
                id host port path query method
                raw
                response {
                    statusCode
                    raw
                }
            }
        }
        """
        result = await self._graphql(query, {"id": request_id})
        return result.get("data", {}).get("request", {})

    async def replay_request(self, request_id: str, modifications: dict = None) -> dict:
        req_data = await self.get_request(request_id)
        if not req_data:
            return {"error": f"Request {request_id} not found"}

        raw = req_data.get("raw", "")
        if modifications:
            for key, value in modifications.items():
                if key == "header":
                    for h_name, h_value in value.items():
                        raw = self._modify_header(raw, h_name, h_value)
                elif key == "body":
                    raw = self._modify_body(raw, value)

        query = """
        mutation SendRequest($input: SendRequestInput!) {
            sendRequest(input: $input) {
                id
                response {
                    statusCode
                    raw
                }
            }
        }
        """
        host = req_data.get("host", "")
        port = req_data.get("port", 443)
        tls = port == 443

        result = await self._graphql(query, {
            "input": {"host": host, "port": port, "tls": tls, "raw": raw}
        })
        return result.get("data", {}).get("sendRequest", {})

    async def fuzz_request(self, request_id: str, parameter: str, wordlist: list[str], marker: str = "\u00a7FUZZ\u00a7") -> list[dict]:
        req_data = await self.get_request(request_id)
        if not req_data:
            return [{"error": f"Request {request_id} not found"}]

        raw_template = req_data.get("raw", "")
        host = req_data.get("host", "")
        port = req_data.get("port", 443)
        tls = port == 443

        results = []
        for payload in wordlist[:100]:
            raw = raw_template.replace(marker, payload)
            if marker not in raw_template:
                raw = raw_template.replace(parameter, payload)

            query = """
            mutation SendRequest($input: SendRequestInput!) {
                sendRequest(input: $input) {
                    id
                    response { statusCode length }
                }
            }
            """
            try:
                result = await self._graphql(query, {
                    "input": {"host": host, "port": port, "tls": tls, "raw": raw}
                })
                resp = result.get("data", {}).get("sendRequest", {}).get("response", {})
                results.append({
                    "payload": payload,
                    "status": resp.get("statusCode", 0),
                    "length": resp.get("length", 0),
                })
            except Exception:
                continue

        return results

    async def get_scope(self) -> list[dict]:
        query = "{ scope { allowlist disallowlist } }"
        result = await self._graphql(query)
        return result.get("data", {}).get("scope", {})

    async def set_scope(self, allowlist: list[str]) -> bool:
        query = """
        mutation UpdateScope($input: UpdateScopeInput!) {
            updateScope(input: $input) { allowlist }
        }
        """
        result = await self._graphql(query, {"input": {"allowlist": allowlist}})
        return "errors" not in result

    def _modify_header(self, raw: str, name: str, value: str) -> str:
        lines = raw.split("\r\n")
        found = False
        for i, line in enumerate(lines):
            if line.lower().startswith(f"{name.lower()}:"):
                lines[i] = f"{name}: {value}"
                found = True
                break
        if not found and len(lines) > 1:
            lines.insert(1, f"{name}: {value}")
        return "\r\n".join(lines)

    def _modify_body(self, raw: str, new_body: str) -> str:
        parts = raw.split("\r\n\r\n", 1)
        if len(parts) == 2:
            return parts[0] + "\r\n\r\n" + new_body
        return raw + "\r\n\r\n" + new_body

    @property
    def connected(self) -> bool:
        return self._connected

    def format_requests(self, requests: list[dict]) -> str:
        if not requests:
            return "No requests found."
        lines = [f"  {'ID':<8} {'Method':<7} {'Status':<6} {'Host':<30} Path"]
        lines.append("  " + "\u2500" * 80)
        for r in requests:
            lines.append(f"  {r['id']:<8} {r['method']:<7} {r['status']:<6} {r['host']:<30} {r['path']}")
        return "\n".join(lines)
