"""Settings, read from environment variables so nothing secret lives in the code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Where this MCP endpoint is reachable. Tokens must be issued for exactly this resource (RFC 8707).
    resource_url: str = "http://127.0.0.1:8000/mcp"
    # The authorization server that issues tokens (in production: Keycloak, Entra ID, Okta...).
    issuer: str = "http://127.0.0.1:9000"
    # Public key used to verify token signatures (RS256).
    public_key_path: Path = Path("keys/public.pem")
    # OpenAI-compatible inference endpoint. Ollama and vLLM both expose one.
    backend_base_url: str = "http://127.0.0.1:11434/v1"
    registry_path: Path = Path("models.yaml")
    audit_log_path: Path = Path("audit.log.jsonl")
    # Per-client rate limit for model calls.
    rate_limit_per_minute: int = 20
    backend: str = "openai"  # "openai" (Ollama/vLLM) or "fake" (tests and demos without a model)
    scopes: tuple[str, ...] = field(default=("models:read", "models:invoke"))

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        return cls(
            resource_url=env.get("GATEWAY_RESOURCE_URL", cls.resource_url),
            issuer=env.get("GATEWAY_ISSUER", cls.issuer),
            public_key_path=Path(env.get("GATEWAY_PUBLIC_KEY", str(cls.public_key_path))),
            backend_base_url=env.get("GATEWAY_BACKEND_URL", cls.backend_base_url),
            registry_path=Path(env.get("GATEWAY_REGISTRY", str(cls.registry_path))),
            audit_log_path=Path(env.get("GATEWAY_AUDIT_LOG", str(cls.audit_log_path))),
            rate_limit_per_minute=int(env.get("GATEWAY_RATE_LIMIT", cls.rate_limit_per_minute)),
            backend=env.get("GATEWAY_BACKEND", cls.backend),
        )
