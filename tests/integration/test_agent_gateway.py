"""Integration tests for the local agent gateway router and the action library.

Uses ``httpx.ASGITransport`` against the FastAPI app for the HTTP-level
tests, and direct router invocations with mocked LLM clients for the
routing-decision tests. The Ollama and Claude clients themselves are
exercised at the router boundary, never against real services.
"""

from __future__ import annotations

import httpx
import pytest

from creative_workflow.worker.agent_gateway.llm.envelope import LLMEnvelope
from creative_workflow.worker.agent_gateway.llm.claude_client import ClaudeUnavailable
from creative_workflow.worker.agent_gateway.llm.ollama_client import (
    OllamaParseError,
    OllamaUnreachable,
)
from creative_workflow.worker.agent_gateway.router import Router
from creative_workflow.worker.agent_gateway.schemas import (
    ChatRequest,
    DocumentContext,
)
from creative_workflow.worker.agent_gateway.server import build_app


# ---------- Test doubles ----------


class _StubOllama:
    def __init__(self, envelope: LLMEnvelope | None = None, exc: Exception | None = None):
        self.envelope = envelope
        self.exc = exc
        self.calls = 0

    async def ask(self, _req: ChatRequest) -> LLMEnvelope:
        self.calls += 1
        if self.exc:
            raise self.exc
        assert self.envelope is not None
        return self.envelope


class _StubClaude:
    def __init__(self, envelope: LLMEnvelope | None = None, exc: Exception | None = None):
        self.envelope = envelope
        self.exc = exc
        self.calls: list[tuple[ChatRequest, str]] = []

    async def ask(self, req: ChatRequest, *, complexity: str = "mechanical") -> LLMEnvelope:
        self.calls.append((req, complexity))
        if self.exc:
            raise self.exc
        assert self.envelope is not None
        return self.envelope


def _doc_context() -> DocumentContext:
    return DocumentContext(
        document_name="hero.psd",
        document_width=1080,
        document_height=1080,
        active_layer="Hero/Product",
    )


# ---------- HTTP-level tests ----------


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    transport = httpx.ASGITransport(app=build_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


# ---------- Router tests ----------


@pytest.mark.asyncio
async def test_ollama_returns_local_action_no_claude_call() -> None:
    ollama = _StubOllama(
        envelope=LLMEnvelope(
            action_type="crop",
            params={"side": "right", "percent": 5},
            needs_claude=False,
            complexity="mechanical",
            explanation="Cropping right by 5%.",
        )
    )
    claude = _StubClaude()
    router = Router(ollama=ollama, claude=claude)  # type: ignore[arg-type]

    resp = await router.route(
        ChatRequest(message="crop tighter on the right by 5", context=_doc_context())
    )

    assert ollama.calls == 1
    assert claude.calls == []
    assert resp.kind == "action"
    assert resp.routed_to == "ollama"
    assert resp.action is not None
    assert resp.action.type == "crop"
    assert resp.action.params["bounds"]["right"] == 1080 - 54  # 5% of 1080


@pytest.mark.asyncio
async def test_ollama_escalates_to_claude_with_complexity_hint() -> None:
    ollama = _StubOllama(
        envelope=LLMEnvelope(
            action_type=None,
            params={},
            needs_claude=True,
            complexity="creative",
            explanation="Composition rework — escalating.",
        )
    )
    claude = _StubClaude(
        envelope=LLMEnvelope(
            action_type="noop",
            params={"echo": "asked-claude"},
            needs_claude=False,
            complexity="creative",
            explanation="Suggested layout in the chat above.",
        )
    )
    router = Router(ollama=ollama, claude=claude)  # type: ignore[arg-type]

    resp = await router.route(
        ChatRequest(message="rework this layout for impact", context=_doc_context())
    )

    assert ollama.calls == 1
    assert len(claude.calls) == 1
    assert claude.calls[0][1] == "creative"
    assert resp.routed_to == "claude"


@pytest.mark.asyncio
async def test_mechanical_escalation_uses_sonnet_complexity() -> None:
    ollama = _StubOllama(
        envelope=LLMEnvelope(
            action_type=None,
            params={},
            needs_claude=True,
            complexity="mechanical",
            explanation="Need clarification — escalating.",
        )
    )
    claude = _StubClaude(
        envelope=LLMEnvelope(
            action_type="get_context",
            params={},
            needs_claude=False,
            complexity="mechanical",
            explanation="Reading active document.",
        )
    )
    router = Router(ollama=ollama, claude=claude)  # type: ignore[arg-type]

    resp = await router.route(
        ChatRequest(message="what's the doc state?", context=_doc_context())
    )

    assert claude.calls[0][1] == "mechanical"
    assert resp.kind == "action"
    assert resp.action is not None
    assert resp.action.type == "get_context"


@pytest.mark.asyncio
async def test_off_allowlist_action_is_rejected() -> None:
    ollama = _StubOllama(
        envelope=LLMEnvelope(
            action_type="delete_layer",  # not on the allowlist
            params={"layer": "Hero/Product"},
            needs_claude=False,
            complexity="mechanical",
            explanation="Removing layer.",
        )
    )
    router = Router(ollama=ollama, claude=_StubClaude())  # type: ignore[arg-type]

    resp = await router.route(
        ChatRequest(message="delete the hero layer", context=_doc_context())
    )

    assert resp.kind == "message"
    assert resp.routed_to == "rejected"
    assert "not allowed" in (resp.text or "").lower()


@pytest.mark.asyncio
async def test_param_out_of_range_returns_validation_error() -> None:
    ollama = _StubOllama(
        envelope=LLMEnvelope(
            action_type="crop",
            params={"side": "right", "percent": 99},  # over the 50% cap
            needs_claude=False,
            complexity="mechanical",
            explanation="Cropping.",
        )
    )
    router = Router(ollama=ollama, claude=_StubClaude())  # type: ignore[arg-type]

    resp = await router.route(
        ChatRequest(message="crop 99% off the right", context=_doc_context())
    )

    assert resp.kind == "message"
    assert resp.action is not None
    assert resp.action.status == "validation_error"


@pytest.mark.asyncio
async def test_ollama_unreachable_falls_back_to_claude_creative() -> None:
    ollama = _StubOllama(exc=OllamaUnreachable("connection refused"))
    claude = _StubClaude(
        envelope=LLMEnvelope(
            action_type="crop",
            params={"side": "right", "percent": 5},
            needs_claude=False,
            complexity="mechanical",
            explanation="Cropping right by 5%.",
        )
    )
    router = Router(ollama=ollama, claude=claude)  # type: ignore[arg-type]

    resp = await router.route(
        ChatRequest(message="crop 5% right", context=_doc_context())
    )

    # On Ollama outage we don't have a complexity hint, so we treat it
    # as creative (better safe — Opus). Claude was still called once.
    assert claude.calls[0][1] == "creative"
    assert resp.routed_to == "claude"
    assert resp.action is not None
    assert resp.action.type == "crop"


@pytest.mark.asyncio
async def test_ollama_parse_error_falls_back_to_claude() -> None:
    ollama = _StubOllama(exc=OllamaParseError("bad json"))
    claude = _StubClaude(
        envelope=LLMEnvelope(
            action_type="noop",
            params={"echo": "ok"},
            needs_claude=False,
            complexity="mechanical",
            explanation="ok.",
        )
    )
    router = Router(ollama=ollama, claude=claude)  # type: ignore[arg-type]

    resp = await router.route(ChatRequest(message="hi", context=_doc_context()))

    assert len(claude.calls) == 1
    assert resp.routed_to == "claude"


@pytest.mark.asyncio
async def test_both_offline_returns_friendly_diagnostic() -> None:
    ollama = _StubOllama(exc=OllamaUnreachable("connection refused"))
    claude = _StubClaude(exc=ClaudeUnavailable("ANTHROPIC_API_KEY not set"))
    router = Router(ollama=ollama, claude=claude)  # type: ignore[arg-type]

    resp = await router.route(ChatRequest(message="hi", context=_doc_context()))

    assert resp.kind == "message"
    assert resp.routed_to == "rejected"
    assert "ollama" in (resp.text or "").lower()
    assert "anthropic_api_key" in (resp.text or "").lower()
