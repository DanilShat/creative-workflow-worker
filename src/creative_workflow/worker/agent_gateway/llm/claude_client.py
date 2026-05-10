"""Claude client for the escalation tier.

Picks the model based on the local model's complexity hint:
- complexity="mechanical" -> Claude Sonnet 4 (fast, cheaper)
- complexity="creative"   -> Claude Opus 4.1 (sharper)

Reads ANTHROPIC_API_KEY from the environment. Returns the same
:class:`LLMEnvelope` shape as the local client so the router doesn't
branch on which tier answered.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from creative_workflow.worker.agent_gateway.llm.envelope import Complexity, LLMEnvelope
from creative_workflow.worker.agent_gateway.llm.prompts import (
    build_user_prompt,
    cloud_system_prompt,
)
from creative_workflow.worker.agent_gateway.schemas import ChatRequest


SONNET_MODEL = os.getenv("CLAUDE_SONNET_MODEL", "claude-sonnet-4-20250514")
OPUS_MODEL = os.getenv("CLAUDE_OPUS_MODEL", "claude-opus-4-1-20250805")


def _model_for(complexity: Complexity) -> str:
    return OPUS_MODEL if complexity == "creative" else SONNET_MODEL


class ClaudeUnavailable(RuntimeError):
    """Raised when Claude can't be reached or no API key is configured."""


class ClaudeParseError(RuntimeError):
    """Raised when Claude returns non-JSON or a non-conforming envelope."""


class ClaudeClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        sonnet_model: str = SONNET_MODEL,
        opus_model: str = OPUS_MODEL,
        max_tokens: int = 512,
    ) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self._sonnet = sonnet_model
        self._opus = opus_model
        self._max_tokens = max_tokens
        self._client = None  # lazy: import at first use so unit tests can mock

    def _ensure_client(self):
        if self._client is None:
            if not self._api_key:
                raise ClaudeUnavailable(
                    "ANTHROPIC_API_KEY is not set on the designer laptop. "
                    "Set it in .env.worker or the shell environment to enable escalation."
                )
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise ClaudeUnavailable("anthropic SDK not installed") from exc
            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def ask(
        self,
        req: ChatRequest,
        *,
        complexity: Complexity = "mechanical",
    ) -> LLMEnvelope:
        client = self._ensure_client()
        model = self._opus if complexity == "creative" else self._sonnet

        message = await client.messages.create(
            model=model,
            max_tokens=self._max_tokens,
            system=cloud_system_prompt(),
            messages=[{"role": "user", "content": build_user_prompt(req)}],
        )

        text = ""
        for block in message.content:
            # Defensively support either dict-shaped or attribute-shaped blocks.
            if isinstance(block, dict):
                if block.get("type") == "text":
                    text += block.get("text", "")
            else:
                if getattr(block, "type", None) == "text":
                    text += getattr(block, "text", "")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ClaudeParseError(f"claude reply not parseable JSON: {text[:200]}") from exc

        try:
            envelope = LLMEnvelope.model_validate(data)
        except Exception as exc:
            raise ClaudeParseError(f"claude envelope invalid: {exc}") from exc

        envelope.needs_claude = False  # we ARE claude
        return envelope
