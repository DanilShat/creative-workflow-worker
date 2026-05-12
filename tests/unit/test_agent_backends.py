from __future__ import annotations

from creative_workflow.worker.agent_runtime.backends import (
    CliAgentBackend,
    LocalOllamaBackend,
)
from creative_workflow.worker.agent_runtime.schemas import AgentChatRequest


def test_cli_backend_probe_reports_missing_binary() -> None:
    backend = CliAgentBackend(name="codex_cli", executable="codex", runner=lambda *_args: (127, "", "not found"))

    status = backend.probe()

    assert status.name == "codex_cli"
    assert status.available is False
    assert status.installed is False
    assert "not found" in (status.reason or "").lower()


def test_cli_backend_probe_reports_not_logged_in() -> None:
    def runner(args, _input=None, _timeout_s=30):
        if "--version" in args:
            return 0, "codex 1.0", ""
        return 1, "", "not logged in"

    backend = CliAgentBackend(name="codex_cli", executable="codex", runner=runner, status_args=("status",))

    status = backend.probe()

    assert status.installed is True
    assert status.logged_in is False
    assert status.available is False
    assert "not logged in" in (status.reason or "").lower()


def test_cli_backend_probe_does_not_block_when_status_subcommand_is_missing() -> None:
    def runner(args, _input=None, _timeout_s=30):
        if "--version" in args:
            return 0, "codex 1.0", ""
        return 2, "", "unrecognized subcommand 'status'"

    backend = CliAgentBackend(name="codex_cli", executable="codex", runner=runner, status_args=("status",))

    status = backend.probe()

    assert status.available is True
    assert status.installed is True
    assert status.logged_in is True


def test_cli_backend_chat_uses_subscription_cli_command() -> None:
    captured = {}

    def runner(args, input_text=None, _timeout_s=120):
        captured["args"] = args
        captured["input"] = input_text
        return 0, "agent reply", ""

    backend = CliAgentBackend(name="claude_cli", executable="claude", runner=runner)

    result = backend.chat(AgentChatRequest(message="help with browser task", task_id="task_1"))

    assert captured["args"][0] == "claude"
    assert "task_1" in captured["input"]
    assert "help with browser task" in captured["input"]
    assert result.routed_to == "claude_cli"
    assert result.text == "agent reply"


def test_local_ollama_backend_probe_uses_healthcheck() -> None:
    backend = LocalOllamaBackend(
        healthcheck=lambda: (False, "connection refused"),
        generate=lambda _prompt: "unused",
    )

    status = backend.probe()

    assert status.name == "local_ollama"
    assert status.available is False
    assert status.installed is False
    assert status.reason == "connection refused"
