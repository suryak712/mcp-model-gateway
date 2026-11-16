"""Token verification. The MCP server is an OAuth 2.1 *resource server*: it never signs anyone in
and never issues tokens. It checks each bearer token and decides whether to trust it."""

from __future__ import annotations

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier


class JWTTokenVerifier(TokenVerifier):
    """Verifies RS256-signed JWT access tokens issued by a known authorization server.

    A token is accepted only if:
      * its signature verifies against the authorization server's public key,
      * it was issued by the expected issuer (`iss`),
      * it was issued for this MCP server (`aud` == our resource URL, per RFC 8707),
      * it has not expired (`exp`).
    Scopes are carried in the standard space-separated `scope` claim.
    """

    def __init__(self, public_key_pem: str, issuer: str, audience: str):
        self._key = public_key_pem
        self._issuer = issuer
        self._audience = audience

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(
                token,
                self._key,
                algorithms=["RS256"],  # never accept "none" or symmetric algorithms here
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError:
            return None  # the SDK turns this into a 401 with a WWW-Authenticate header

        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id", claims["sub"])),
            subject=str(claims["sub"]),
            scopes=str(claims.get("scope", "")).split(),
            expires_at=int(claims["exp"]),
            resource=self._audience,
            claims=claims,
        )
