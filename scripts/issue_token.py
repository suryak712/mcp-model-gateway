"""DEV ONLY. Signs a short-lived access token, standing in for a real authorization server.

Examples:
  python scripts/issue_token.py --client analytics-agent --scope "models:read models:invoke"
  python scripts/issue_token.py --client read-only-bot --scope "models:read"
  python scripts/issue_token.py --client wrong-audience --aud http://example.com/other
"""

import argparse
import time
from pathlib import Path

import jwt

p = argparse.ArgumentParser()
p.add_argument("--client", required=True)
p.add_argument("--scope", default="models:read models:invoke")
p.add_argument("--aud", default="http://127.0.0.1:8000/mcp")
p.add_argument("--iss", default="http://127.0.0.1:9000")
p.add_argument("--ttl", type=int, default=3600, help="seconds until the token expires")
a = p.parse_args()

now = int(time.time())
token = jwt.encode(
    {"iss": a.iss, "aud": a.aud, "sub": a.client, "client_id": a.client, "scope": a.scope,
     "iat": now, "exp": now + a.ttl},
    Path("keys/private.pem").read_text(),
    algorithm="RS256",
)
print(token)
