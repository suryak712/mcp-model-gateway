"""Calls the gateway like an agent would, using the official MCP client.

  TOKEN=$(python scripts/issue_token.py --client demo-agent)
  python scripts/demo_client.py "$TOKEN" --model qwen-small --prompt "Explain MCP in one sentence."
"""

import argparse
import asyncio

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

p = argparse.ArgumentParser()
p.add_argument("token")
p.add_argument("--url", default="http://127.0.0.1:8000/mcp")
p.add_argument("--model", default="qwen-small")
p.add_argument("--prompt", default="Explain the Model Context Protocol in one sentence.")
a = p.parse_args()


async def main() -> None:
    headers = {"Authorization": f"Bearer {a.token}"}
    async with (
        httpx.AsyncClient(headers=headers, timeout=180) as http,
        streamable_http_client(a.url, http_client=http) as (read, write, *_),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        print("Tools:", ", ".join(t.name for t in tools.tools))

        models = await session.call_tool("list_models", {})
        print("\nlist_models ->", "DENIED" if models.is_error else "ok")
        print(models.content[0].text[:600])

        result = await session.call_tool("generate", {"model": a.model, "prompt": a.prompt})
        print(f"\ngenerate({a.model}) ->", "DENIED" if result.is_error else "ok")
        print(result.content[0].text[:600])


asyncio.run(main())
