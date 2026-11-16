import json

import anyio
import pytest
from mcp.server.auth.provider import AccessToken

from gateway.server import build_service
from gateway.service import GatewayDenied


def token(scopes, client="agent-1"):
    return AccessToken(token="t", client_id=client, scopes=scopes)


def run(coro_fn, *args):
    return anyio.run(coro_fn, *args)


def test_list_models_requires_read_scope(settings):
    svc = build_service(settings)
    assert {m["alias"] for m in svc.list_models(token(["models:read"]))} == {"on-model", "off-model"}
    with pytest.raises(GatewayDenied, match="models:read"):
        svc.list_models(token(["models:invoke"]))
    with pytest.raises(GatewayDenied, match="Not authenticated"):
        svc.list_models(None)


def test_generate_requires_invoke_scope(settings):
    svc = build_service(settings)
    with pytest.raises(GatewayDenied, match="models:invoke"):
        run(svc.generate, token(["models:read"]), "on-model", "hi", 10)


def test_generate_happy_path_and_audit(settings):
    svc = build_service(settings)
    out = run(svc.generate, token(["models:invoke"]), "on-model", "hello", 10)
    assert out["model"] == "on-model"
    assert "hello" in out["text"]
    event = json.loads(settings.audit_log_path.read_text().splitlines()[-1])
    assert event["outcome"] == "ok" and event["client_id"] == "agent-1"
    assert "hello" not in json.dumps(event)  # prompts are never written to the audit log


def test_kill_switch_and_unknown_model_are_refused(settings):
    svc = build_service(settings)
    with pytest.raises(GatewayDenied, match="kill switch"):
        run(svc.generate, token(["models:invoke"]), "off-model", "hi", 10)
    with pytest.raises(GatewayDenied, match="not in the registry"):
        run(svc.generate, token(["models:invoke"]), "made-up-model", "hi", 10)


def test_rate_limit_is_per_client(settings):
    svc = build_service(settings)  # 3 calls per minute in the test settings
    for _ in range(3):
        run(svc.generate, token(["models:invoke"], client="a"), "on-model", "hi", 10)
    with pytest.raises(GatewayDenied, match="Rate limit"):
        run(svc.generate, token(["models:invoke"], client="a"), "on-model", "hi", 10)
    # another client still has its own budget
    run(svc.generate, token(["models:invoke"], client="b"), "on-model", "hi", 10)


def test_output_is_capped_by_registry(settings):
    seen = {}

    class Spy:
        async def complete(self, model, prompt, max_tokens):
            seen["max_tokens"] = max_tokens
            from gateway.backends import Completion
            return Completion("ok", model, 1.0, 1, 1)

    svc = build_service(settings, backend=Spy())
    run(svc.generate, token(["models:invoke"]), "on-model", "hi", 10_000)
    assert seen["max_tokens"] == 64


def test_backend_failure_is_contained(settings):
    class Broken:
        async def complete(self, model, prompt, max_tokens):
            raise ConnectionError("model server down")

    svc = build_service(settings, backend=Broken())
    with pytest.raises(GatewayDenied, match="unavailable"):
        run(svc.generate, token(["models:invoke"]), "on-model", "hi", 10)
