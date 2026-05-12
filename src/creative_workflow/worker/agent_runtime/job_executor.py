"""Executor that adapts server agent-chat jobs to local agent backends."""

from __future__ import annotations

import os
from typing import Any

from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import FailureType
from creative_workflow.worker.agent_runtime.backends import CliAgentBackend, LocalOllamaBackend
from creative_workflow.worker.agent_runtime.router import AgentRuntime, AgentRuntimeError
from creative_workflow.worker.agent_runtime.schemas import AgentBackend, AgentChatRequest, AgentName
from creative_workflow.worker.browser.flows.base import BrowserFlowError
from creative_workflow.worker.config import WorkerSettings


AGENT_CHAT_ACTION = "designer_agent_chat"
AGENT_CHAT_CAPABILITY = "agent.chat"


class AgentChatJobExecutor:
    """Run a worker job through local Ollama, Claude Code CLI, or Codex CLI."""

    def __init__(self, settings: WorkerSettings, runtime: AgentRuntime | None = None) -> None:
        self.settings = settings
        self.runtime = runtime or AgentRuntime(_default_backends(), settings.worker_temp_root / "agent_usage.json")

    def run(self, job: JobForWorker) -> dict[str, Any]:
        message = str(job.inputs.get("message") or "").strip()
        if not message:
            raise BrowserFlowError(FailureType.INVALID_JOB_PAYLOAD, "designer_agent_chat requires a non-empty message.")
        preferred_agent = job.inputs.get("preferred_agent") or None
        try:
            request = AgentChatRequest(
                message=message,
                task_id=job.task_id,
                context=dict(job.inputs.get("context") or {}),
                preferred_agent=preferred_agent,
            )
            result = self.runtime.chat(request)
        except (AgentRuntimeError, RuntimeError) as exc:
            raise BrowserFlowError(FailureType.DEPENDENCY_UNAVAILABLE, str(exc)) from exc
        return {
            "agent_chat": {
                "agent": result.agent,
                "routed_to": result.routed_to,
                "text": result.text,
                "raw_output": result.raw_output,
            }
        }


def _default_backends() -> list[AgentBackend]:
    """Build production backends from local environment defaults.

    The executable names are configurable because Windows installs can expose
    different shims depending on whether the tool was installed with npm, a
    standalone installer, or a package manager.
    """

    return [
        LocalOllamaBackend(),
        CliAgentBackend(
            name="claude_cli",
            executable=os.getenv("CLAUDE_CLI_EXECUTABLE", "claude"),
            status_args=_split_args(os.getenv("CLAUDE_CLI_STATUS_ARGS", "auth status")),
            chat_args=_split_args(os.getenv("CLAUDE_CLI_CHAT_ARGS", "--print --permission-mode dontAsk")),
        ),
        CliAgentBackend(
            name="codex_cli",
            executable=os.getenv("CODEX_CLI_EXECUTABLE", "codex"),
            status_args=_split_args(os.getenv("CODEX_CLI_STATUS_ARGS", "login status")),
            chat_args=_split_args(os.getenv("CODEX_CLI_CHAT_ARGS", "exec --ask-for-approval never --sandbox read-only -")),
        ),
    ]


def _split_args(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split(" ") if item)
