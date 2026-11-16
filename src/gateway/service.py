"""The gateway's business logic, kept separate from MCP wiring so it can be unit-tested directly.
Every call goes through the same checks, in this order:
scope -> rate limit -> registry (allowlist + kill switch) -> output cap -> backend -> audit."""

from __future__ import annotations

from dataclasses import asdict

from mcp.server.auth.provider import AccessToken

from .audit import AuditLog
from .backends import Backend
from .ratelimit import RateLimiter
from .registry import ModelNotAllowed, Registry


class GatewayDenied(Exception):
    """A request was refused by a gateway control. The message is safe to show the caller."""


class GatewayService:
    def __init__(self, registry: Registry, backend: Backend, limiter: RateLimiter, audit: AuditLog):
        self.registry = registry
        self.backend = backend
        self.limiter = limiter
        self.audit = audit

    @staticmethod
    def _require_scope(token: AccessToken | None, scope: str) -> AccessToken:
        if token is None:
            raise GatewayDenied("Not authenticated.")
        if scope not in token.scopes:
            raise GatewayDenied(f"Token is missing the '{scope}' scope.")
        return token

    def list_models(self, token: AccessToken | None) -> list[dict]:
        token = self._require_scope(token, "models:read")
        self.audit.record(event="list_models", client_id=token.client_id, outcome="ok")
        return [{"alias": alias, **asdict(entry)} for alias, entry in self.registry.list().items()]

    async def generate(self, token: AccessToken | None, model: str, prompt: str, max_tokens: int) -> dict:
        token = self._require_scope(token, "models:invoke")
        base = {"event": "generate", "client_id": token.client_id, "model": model}

        if not self.limiter.allow(token.client_id):
            self.audit.record(**base, outcome="rate_limited")
            raise GatewayDenied("Rate limit exceeded. Try again shortly.")
        try:
            entry = self.registry.resolve(model)
        except ModelNotAllowed as e:
            self.audit.record(**base, outcome="model_not_allowed")
            raise GatewayDenied(str(e)) from e

        capped = max(1, min(max_tokens, entry.max_output_tokens))
        try:
            result = await self.backend.complete(entry.name, prompt, capped)
        except Exception as e:  # the backend is down, timed out, or rejected the request
            self.audit.record(**base, outcome="backend_error", error=type(e).__name__)
            raise GatewayDenied("The model backend is unavailable.") from e

        self.audit.record(
            **base,
            outcome="ok",
            latency_ms=round(result.latency_ms, 1),
            prompt_chars=len(prompt),
            output_chars=len(result.text),
            completion_tokens=result.completion_tokens,
        )
        return {
            "model": model,
            "text": result.text,
            "latency_ms": round(result.latency_ms, 1),
            "completion_tokens": result.completion_tokens,
        }
