"""DEV ONLY. Creates an RSA key pair standing in for your authorization server's signing key.
In production the authorization server (Keycloak, Entra ID, Okta...) holds the private key and
publishes the public key; the MCP server only ever needs the public half."""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

out = Path("keys")
out.mkdir(exist_ok=True)
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
(out / "private.pem").write_bytes(
    key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                      serialization.NoEncryption())
)
(out / "public.pem").write_bytes(
    key.public_key().public_bytes(serialization.Encoding.PEM,
                                  serialization.PublicFormat.SubjectPublicKeyInfo)
)
print("Wrote keys/private.pem and keys/public.pem (keys/ is git-ignored).")
