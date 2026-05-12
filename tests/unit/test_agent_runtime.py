from __future__ import annotations

from pathlib import Path

import pytest

from creative_workflow.worker.agent_runtime.router import (
    AgentRuntime,
    AgentRuntimeError,
)
from creative_workflow.worker.agent_runtime.schemas import (
    AgentBackendStatus,
    AgentChatRequest,
    AgentCommandResult,
)


class FakeBackend:
    def __init__(self, status: AgentBackendStatus, reply: str = "ok") -> None:
        self.name = status.name
        self.status = status
        self.reply = reply
        self.calls: list[AgentChatRequest] = []

    def probe(self) -> AgentBackendStatus:
        return self.status

    def chat(self, request: AgentChatRequest) -> AgentCommandResult:
        self.calls.append(request)
        return AgentCommandResult(
            agent=self.name,
            text=self.reply,
            routed_to=self.name,
            raw_output=self.reply,
        )


def test_agent_runtime_routes_to_cli_when_worker_receives_escalation(tmp_path: Path) -> None:
    claude = FakeBackend(
        AgentBackendStatus(name="claude_cli", available=True, installed=True, logged_in=True),
        reply="claude answer",
    )
    runtime = AgentRuntime([claude], usage_path=tmp_path / "usage.json")

    result = runtime.chat(AgentChatRequest(message="inspect this browser task"))

    assert result.routed_to == "claude_cli"
    assert result.text == "claude answer"
    assert len(claude.calls) == 1


def test_agent_runtime_routes_browser_requests_to_least_used_cli_agent(tmp_path: Path) -> None:
    usage = tmp_path / "usage.json"
    usage.write_text(
        '{"claude_cli":{"successes":3,"failures":0},"codex_cli":{"successes":0,"failures":0}}',
        encoding="utf-8",
    )
    claude = FakeBackend(
        AgentBackendStatus(name="claude_cli", available=True, installed=True, logged_in=True),
        reply="claude browser plan",
    )
    codex = FakeBackend(
        AgentBackendStatus(name="codex_cli", available=True, installed=True, logged_in=True),
        reply="codex browser plan",
    )
    runtime = AgentRuntime([claude, codex], usage_path=usage)

    result = runtime.chat(AgentChatRequest(message="open browser and inspect freepik"))

    assert result.routed_to == "codex_cli"
    assert result.text == "codex browser plan"
    assert codex.calls[0].message.startswith("open browser")


def test_agent_runtime_skips_not_logged_in_cli_and_falls_back(tmp_path: Path) -> None:
    codex = FakeBackend(
        AgentBackendStatus(
            name="codex_cli",
            available=False,
            installed=True,
            logged_in=False,
            reason="Codex CLI is installed but not logged in.",
        )
    )
    claude = FakeBackend(
        AgentBackendStatus(name="claude_cli", available=True, installed=True, logged_in=True),
        reply="claude fallback",
    )
    runtime = AgentRuntime([codex, claude], usage_path=tmp_path / "usage.json")

    result = runtime.chat(AgentChatRequest(message="use browser to inspect the page"))

    assert result.routed_to == "claude_cli"
    assert result.text == "claude fallback"


def test_agent_runtime_reports_all_unavailable_without_api_key_requirement(tmp_path: Path) -> None:
    runtime = AgentRuntime(
        [
            FakeBackend(
                AgentBackendStatus(
                    name="codex_cli",
                    available=False,
                    installed=False,
                    logged_in=False,
                    reason="Codex CLI not found on PATH.",
                )
            ),
            FakeBackend(
                AgentBackendStatus(
                    name="claude_cli",
                    available=False,
                    installed=True,
                    logged_in=False,
                    reason="Claude Code is installed but not logged in.",
                )
            ),
        ],
        usage_path=tmp_path / "usage.json",
    )

    with pytest.raises(AgentRuntimeError) as exc:
        runtime.chat(AgentChatRequest(message="please help"))

    message = str(exc.value)
    assert "Codex CLI not found" in message
    assert "Claude Code is installed but not logged in" in message
    assert "API key" not in message
