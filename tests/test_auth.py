import anyio
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from gateway.auth import JWTTokenVerifier

from .conftest import ISSUER, RESOURCE


def verify(keypair, token):
    v = JWTTokenVerifier(public_key_pem=keypair[1], issuer=ISSUER, audience=RESOURCE)
    return anyio.run(v.verify_token, token)


def test_valid_token_is_accepted_with_scopes(keypair, make_token):
    at = verify(keypair, make_token(scope="models:read models:invoke", client="bot-7"))
    assert at is not None
    assert at.client_id == "bot-7"
    assert set(at.scopes) == {"models:read", "models:invoke"}
    assert at.resource == RESOURCE


def test_token_for_another_resource_is_rejected(keypair, make_token):
    assert verify(keypair, make_token(aud="http://example.com/other-mcp")) is None


def test_token_from_unknown_issuer_is_rejected(keypair, make_token):
    assert verify(keypair, make_token(iss="http://evil.example.com")) is None


def test_expired_token_is_rejected(keypair, make_token):
    assert verify(keypair, make_token(ttl=-10)) is None


def test_token_signed_by_another_key_is_rejected(keypair, make_token):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = other.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption())
    forged = jwt.encode({"iss": ISSUER, "aud": RESOURCE, "sub": "x", "exp": 9999999999}, pem, algorithm="RS256")
    assert verify(keypair, forged) is None


def test_unsigned_token_is_rejected(keypair):
    unsigned = jwt.encode({"iss": ISSUER, "aud": RESOURCE, "sub": "x", "exp": 9999999999}, None, algorithm="none")
    assert verify(keypair, unsigned) is None
