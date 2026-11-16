import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from gateway.config import Settings

RESOURCE = "http://127.0.0.1:8000/mcp"
ISSUER = "http://127.0.0.1:9000"

REGISTRY_YAML = """
models:
  on-model:
    name: "fake-on"
    owner: "test"
    license: "Apache-2.0"
    source: "test"
    enabled: true
    max_output_tokens: 64
  off-model:
    name: "fake-off"
    owner: "test"
    license: "Apache-2.0"
    source: "test"
    enabled: false
    max_output_tokens: 64
"""


@pytest.fixture(scope="session")
def keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    public = key.public_key().public_bytes(serialization.Encoding.PEM,
                                           serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return private, public


@pytest.fixture
def settings(tmp_path: Path, keypair) -> Settings:
    (tmp_path / "public.pem").write_text(keypair[1])
    (tmp_path / "models.yaml").write_text(REGISTRY_YAML)
    return Settings(
        resource_url=RESOURCE,
        issuer=ISSUER,
        public_key_path=tmp_path / "public.pem",
        registry_path=tmp_path / "models.yaml",
        audit_log_path=tmp_path / "audit.jsonl",
        rate_limit_per_minute=3,
        backend="fake",
    )


@pytest.fixture
def make_token(keypair):
    def _make(scope="models:read models:invoke", aud=RESOURCE, iss=ISSUER, ttl=600, client="agent-1"):
        now = int(time.time())
        claims = {"iss": iss, "aud": aud, "sub": client, "client_id": client, "scope": scope,
                  "iat": now, "exp": now + ttl}
        return jwt.encode(claims, keypair[0], algorithm="RS256")
    return _make
