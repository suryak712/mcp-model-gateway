"""Inference backends. Every backend speaks the same small interface, so workloads can move
between models and providers (Ollama on a laptop, vLLM on a GPU server, a hosted API) by
changing configuration, not code."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass(frozen=True)
class Completion:
    text: str
    model: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None


class Backend(Protocol):
    async def complete(self, model: str, prompt: str, max_tokens: int) -> Completion: ...


class OpenAICompatibleBackend:
    """Talks to any server that implements the OpenAI chat-completions API (Ollama, vLLM, ...)."""

    def __init__(self, base_url: str, api_key: str = "not-needed-for-local", timeout: float = 120.0):
        self._client = httpx.AsyncClient(
            base_url=base_url, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"}
        )

    async def complete(self, model: str, prompt: str, max_tokens: int) -> Completion:
        started = time.perf_counter()
        resp = await self._client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0,  # deterministic output makes evaluations reproducible
            },
        )
        resp.raise_for_status()
        body = resp.json()
        usage = body.get("usage") or {}
        return Completion(
            text=body["choices"][0]["message"]["content"],
            model=body.get("model", model),
            latency_ms=(time.perf_counter() - started) * 1000,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )


class FakeBackend:
    """Returns canned answers. Used in tests and CI, where no model is available."""

    def __init__(self, answers: dict[str, str] | None = None):
        self._answers = answers or {}

    async def complete(self, model: str, prompt: str, max_tokens: int) -> Completion:
        text = self._answers.get(prompt, f"[{model}] echo: {prompt}")
        return Completion(text=text, model=model, latency_ms=1.0, prompt_tokens=len(prompt.split()),
                          completion_tokens=len(text.split()))
