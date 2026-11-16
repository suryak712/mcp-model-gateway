"""MCP wiring: exposes the gateway as an OAuth-protected MCP server over streamable HTTP.

Run it with:  python -m gateway.server
"""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import AnyHttpUrl

from .audit import AuditLog
from .auth import JWTTokenVerifier
from .backends import Backend, FakeBackend, OpenAICompatibleBackend
from .config import Settings
from .ratelimit import RateLimiter
from .registry import Registry
from .service import GatewayDenied, GatewayService


def build_service(settings: Settings, backend: Backend | None = None) -> GatewayService:
    if backend is None:
        backend = FakeBackend() if settings.backend == "fake" else OpenAICompatibleBackend(
            settings.backend_base_url
        )
    return GatewayService(
        registry=Registry.load(settings.registry_path),
        backend=backend,
        limiter=RateLimiter(settings.rate_limit_per_minute),
        audit=AuditLog(settings.audit_log_path),
    )


def build_server(settings: Settings, service: GatewayService) -> MCPServer:
    verifier = JWTTokenVerifier(
        public_key_pem=settings.public_key_path.read_text(),
        issuer=settings.issuer,
        audience=settings.resource_url,
    )
    mcp = MCPServer(
        "MCP Model Gateway",
        instructions="Lists approved open-weight models and runs prompts against them, under policy.",
        token_verifier=verifier,
        auth=AuthSettings(
            # Published in Protected Resource Metadata (RFC 9728) so clients can find the auth server.
            issuer_url=AnyHttpUrl(settings.issuer),
            resource_server_url=AnyHttpUrl(settings.resource_url),
            validate_token_resource=True,  # refuse tokens issued for any other resource (RFC 8707)
            required_scopes=["models:read"],  # minimum scope to talk to this server at all
        ),
    )

    @mcp.tool(description="List the open-weight models this gateway may serve, with owner, licence, "
                          "provenance and whether each is currently enabled.")
    def list_models() -> list[dict]:
        try:
            return service.list_models(get_access_token())
        except GatewayDenied as e:
            raise ToolError(str(e)) from e

    @mcp.tool(description="Run a prompt against an approved model. Requires the models:invoke scope.")
    async def generate(model: str, prompt: str, max_tokens: int = 256) -> dict:
        try:
            return await service.generate(get_access_token(), model, prompt, max_tokens)
        except GatewayDenied as e:
            raise ToolError(str(e)) from e

    return mcp


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    server = build_server(settings, build_service(settings))
    uvicorn.run(server.streamable_http_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
