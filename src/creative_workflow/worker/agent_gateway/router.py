"""Request routing — Ollama-first, escalate to Claude only when needed.

Flow per chat request:

1. Send to Ollama (gemma3n:e2b) with JSON output mode.
2. If Ollama parses cleanly and ``needs_claude`` is false, validate the
   action against the allowlist and return.
3. Otherwise (needs_claude=true, parse error, or Ollama unreachable):
   ask Claude. Use the configured Sonnet model for
   ``complexity=mechanical`` requests and the configured Opus model for
   ``creative`` ones. The local model's hint or our own fallback supplies
   the complexity.
4. Off-allowlist action types yield a designer-friendly rejection
   message rather than an exception.

The router is the only place that owns the "which tier answered" choice.
Both clients return the same :class:`LLMEnvelope`, and validation is
delegated to :func:`actions.materialize`.
"""

from __future__ import annotations

import logging

from creative_workflow.worker.agent_gateway.actions import (
    UnknownAction,
    materialize,
)
from creative_workflow.worker.agent_gateway.llm import (
    ClaudeClient,
    LLMEnvelope,
    OllamaClient,
)
from creative_workflow.worker.agent_gateway.llm.claude_client import (
    ClaudeParseError,
    ClaudeUnavailable,
)
from creative_workflow.worker.agent_gateway.llm.ollama_client import (
    OllamaParseError,
    OllamaUnreachable,
)
from creative_workflow.worker.agent_gateway.schemas import ChatRequest, ChatResponse


_log = logging.getLogger(__name__)


class Router:
    def __init__(
        self,
        ollama: OllamaClient | None = None,
        claude: ClaudeClient | None = None,
    ) -> None:
        self.ollama = ollama or OllamaClient()
        self.claude = claude or ClaudeClient()

    async def route(self, req: ChatRequest) -> ChatResponse:
        envelope, ollama_failure = await self._ask_ollama(req)

        if envelope is not None and not envelope.needs_claude:
            return self._materialize_or_reject(envelope, req, source="ollama")

        complexity = envelope.complexity if envelope else "creative"
        try:
            cloud_envelope = await self.claude.ask(req, complexity=complexity)
        except (ClaudeUnavailable, ClaudeParseError) as exc:
            return _offline_message(req, ollama_failure, str(exc))

        return self._materialize_or_reject(cloud_envelope, req, source="claude")

    async def _ask_ollama(
        self, req: ChatRequest
    ) -> tuple[LLMEnvelope | None, str | None]:
        try:
            return await self.ollama.ask(req), None
        except OllamaUnreachable as exc:
            _log.info("ollama unreachable, escalating to claude: %s", exc)
            return None, f"ollama unreachable: {exc}"
        except OllamaParseError as exc:
            _log.info("ollama returned unparseable envelope, escalating: %s", exc)
            return None, f"ollama parse error: {exc}"

    def _materialize_or_reject(
        self,
        envelope: LLMEnvelope,
        req: ChatRequest,
        *,
        source: str,
    ) -> ChatResponse:
        try:
            action = materialize(envelope, req.context)
        except UnknownAction as exc:
            return ChatResponse(
                kind="message",
                text=str(exc),
                action=None,
                routed_to="rejected",
            )

        if action.status != "ok":
            return ChatResponse(
                kind="message",
                text=action.error or action.explanation or "Couldn't validate that action.",
                action=action,
                routed_to=source,  # type: ignore[arg-type]
            )

        return ChatResponse(
            kind="action",
            text=envelope.explanation or action.explanation,
            action=action,
            routed_to=source,  # type: ignore[arg-type]
        )


# Module-level convenience the FastAPI app uses; tests can construct
# their own Router with mocked clients.
async def route_message(req: ChatRequest) -> ChatResponse:
    return await Router().route(req)


def _offline_message(
    req: ChatRequest,
    ollama_failure: str | None,
    claude_failure: str,
) -> ChatResponse:
    return ChatResponse(
        kind="message",
        text=(
            "Both the local model and Claude are unavailable. "
            "Check that Ollama is running on the laptop "
            "(http://127.0.0.1:11434) and that ANTHROPIC_API_KEY is set "
            "for escalation. Diagnostic: "
            f"local={ollama_failure or 'n/a'}; cloud={claude_failure}."
        ),
        action=None,
        routed_to="rejected",
    )
