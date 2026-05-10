"""Ollama client for the local LLM tier (gemma3n:e2b by default).

Uses Ollama's `format: "json"` mode so gemma is forced to emit a JSON
object. We still parse defensively — small models occasionally drop
fields. A parse failure is treated as "needs_claude" by the router.
"""

from __future__ import annotations

import json
import os

import httpx

from creative_workflow.worker.agent_gateway.llm.envelope import LLMEnvelope
from creative_workflow.worker.agent_gateway.llm.prompts import (
    build_user_prompt,
    local_system_prompt,
)
from creative_workflow.worker.agent_gateway.schemas import ChatRequest


class OllamaUnreachable(RuntimeError):
    """Raised when the gateway cannot reach the local Ollama daemon."""


class OllamaParseError(RuntimeError):
    """Raised when Ollama replied but the body is not a usable envelope."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3n:e2b")
        self._timeout_s = timeout_s

    async def ask(self, req: ChatRequest) -> LLMEnvelope:
        body = {
            "model": self.model,
            "system": local_system_prompt(),
            "prompt": build_user_prompt(req),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=body)
        except httpx.HTTPError as exc:
            raise OllamaUnreachable(str(exc)) from exc

        if resp.status_code >= 500:
            raise OllamaUnreachable(f"ollama returned HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise OllamaParseError(f"ollama returned HTTP {resp.status_code}: {resp.text[:200]}")

        try:
            payload = resp.json()
            inner = payload.get("response", "")
            data = json.loads(inner) if isinstance(inner, str) else inner
        except (ValueError, json.JSONDecodeError) as exc:
            raise OllamaParseError(f"ollama response not parseable JSON: {exc}") from exc

        try:
            return LLMEnvelope.model_validate(data)
        except Exception as exc:
            raise OllamaParseError(f"ollama envelope invalid: {exc}") from exc
