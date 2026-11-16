"""End-to-end checks over real HTTP requests to the MCP endpoint."""

import json

from starlette.testclient import TestClient

from gateway.server import build_server, build_service

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "test", "version": "0"}},
}


def app_for(settings):
    return build_server(settings, build_service(settings)).streamable_http_app(json_response=True)


def parse(resp):
    if resp.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line[5:].strip() for line in resp.text.splitlines() if line.startswith("data:")]
        return json.loads(data[-1])
    return resp.json()


def test_protected_resource_metadata_is_published(settings):
    with TestClient(app_for(settings), base_url="http://127.0.0.1:8000") as client:
        r = client.get("/.well-known/oauth-protected-resource/mcp")
        assert r.status_code == 200
        body = r.json()
        assert body["resource"].rstrip("/") == settings.resource_url
        assert any(s.rstrip("/") == settings.issuer for s in body["authorization_servers"])


def test_request_without_token_gets_401_pointing_at_metadata(settings):
    with TestClient(app_for(settings), base_url="http://127.0.0.1:8000") as client:
        r = client.post("/mcp", headers=HEADERS, json=INIT)
        assert r.status_code == 401
        assert "resource_metadata" in r.headers.get("www-authenticate", "")


def test_token_for_wrong_audience_gets_401(settings, make_token):
    with TestClient(app_for(settings), base_url="http://127.0.0.1:8000") as client:
        bad = make_token(aud="http://example.com/other")
        r = client.post("/mcp", headers={**HEADERS, "Authorization": f"Bearer {bad}"}, json=INIT)
        assert r.status_code == 401


def call_tool(client, auth_headers, name, arguments):
    r = client.post("/mcp", headers=auth_headers, json=INIT)
    assert r.status_code == 200, r.text
    session = r.headers.get("mcp-session-id")
    h = {**auth_headers, **({"mcp-session-id": session} if session else {})}
    client.post("/mcp", headers=h, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    r = client.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                             "params": {"name": name, "arguments": arguments}})
    assert r.status_code == 200, r.text
    return parse(r)["result"]


def test_valid_token_can_list_and_invoke_models(settings, make_token):
    with TestClient(app_for(settings), base_url="http://127.0.0.1:8000") as client:
        h = {**HEADERS, "Authorization": f"Bearer {make_token()}"}
        listed = call_tool(client, h, "list_models", {})
        assert not listed.get("isError")
        assert "on-model" in json.dumps(listed)

        gen = call_tool(client, h, "generate", {"model": "on-model", "prompt": "ping"})
        assert not gen.get("isError")
        assert "ping" in json.dumps(gen)


def test_read_only_token_cannot_invoke(settings, make_token):
    with TestClient(app_for(settings), base_url="http://127.0.0.1:8000") as client:
        h = {**HEADERS, "Authorization": f"Bearer {make_token(scope='models:read')}"}
        res = call_tool(client, h, "generate", {"model": "on-model", "prompt": "ping"})
        assert res.get("isError")
        assert "models:invoke" in json.dumps(res)


def test_unexpected_host_header_is_refused(settings, make_token):
    # DNS-rebinding protection: requests addressed to an unknown host never reach the tools.
    with TestClient(app_for(settings), base_url="http://attacker.example") as client:
        h = {**HEADERS, "Authorization": f"Bearer {make_token()}"}
        assert client.post("/mcp", headers=h, json=INIT).status_code == 421
