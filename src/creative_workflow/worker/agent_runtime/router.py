"""Routing policy for local Ollama, Claude Code, and Codex CLI agents."""

from __future__ import annotations

from pathlib import Path

from creative_workflow.worker.agent_runtime.schemas import (
    AgentBackend,
    AgentBackendStatus,
    AgentChatRequest,
    AgentCommandResult,
    AgentName,
)
from creative_workflow.worker.agent_runtime.usage import UsageLedger


class AgentRuntimeError(RuntimeError):
    """Raised when no local agent can handle a chat request."""


class AgentRuntime:
    def __init__(self, backends: list[AgentBackend], usage_path: Path):
        self.backends = backends
        self.usage = UsageLedger(usage_path)

    def chat(self, request: AgentChatRequest) -> AgentCommandResult:
        statuses = {backend.name: backend.probe() for backend in self.backends}
        candidates = self._candidate_backends(request, statuses)
        if not candidates:
            reasons = [status.reason or f"{status.name} unavailable" for status in statuses.values()]
            raise AgentRuntimeError("; ".join(reasons))

        backend = candidates[0]
        try:
            result = backend.chat(request)
        except Exception:
            self.usage.record_failure(backend.name)
            raise
        self.usage.record_success(result.routed_to)
        return result

    def _candidate_backends(
        self,
        request: AgentChatRequest,
        statuses: dict[AgentName, AgentBackendStatus],
    ) -> list[AgentBackend]:
        available = [
            backend
            for backend in self.backends
            if statuses[backend.name].available
        ]
        if request.preferred_agent:
            preferred = [backend for backend in available if backend.name == request.preferred_agent]
            if preferred:
                return preferred

        if self._is_routine_request(request.message):
            local = [backend for backend in available if backend.name == "local_ollama"]
            if local:
                return local

        cli = [backend for backend in available if backend.name in {"claude_cli", "codex_cli"}]
        if cli:
            return sorted(cli, key=lambda backend: self.usage.score(backend.name))

        return available

    def _is_routine_request(self, message: str) -> bool:
        text = message.lower()
        browser_markers = {"browser", "click", "open page", "inspect", "freepik", "gemini", "photoshop", "after effects"}
        creative_markers = {"make variants", "design", "compose", "creative", "layout"}
        return not any(marker in text for marker in browser_markers | creative_markers)
