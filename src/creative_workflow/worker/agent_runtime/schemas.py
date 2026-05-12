"""Typed contracts for local agent routing on the designer laptop."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


AgentName = Literal["local_ollama", "claude_cli", "codex_cli"]


class AgentChatRequest(BaseModel):
    message: str
    task_id: str | None = None
    context: dict = Field(default_factory=dict)
    preferred_agent: AgentName | None = None


class AgentBackendStatus(BaseModel):
    name: AgentName
    available: bool
    installed: bool
    logged_in: bool
    reason: str | None = None
    version: str | None = None
    supports_browser: bool = False


class AgentCommandResult(BaseModel):
    agent: AgentName
    text: str
    routed_to: AgentName
    raw_output: str | None = None


class UsageEntry(BaseModel):
    successes: int = 0
    failures: int = 0


class AgentBackend(Protocol):
    name: AgentName

    def probe(self) -> AgentBackendStatus:
        ...

    def chat(self, request: AgentChatRequest) -> AgentCommandResult:
        ...
