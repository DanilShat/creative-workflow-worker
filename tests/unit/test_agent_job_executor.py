from __future__ import annotations

from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import FailureType, JobType
from creative_workflow.worker.agent_runtime.job_executor import AGENT_CHAT_ACTION, AgentChatJobExecutor
from creative_workflow.worker.agent_runtime.schemas import AgentCommandResult
from creative_workflow.worker.browser.flows.base import BrowserFlowError
from creative_workflow.worker.config import WorkerSettings


class FakeRuntime:
    def __init__(self, result: AgentCommandResult | Exception) -> None:
        self.result = result
        self.requests = []

    def chat(self, request):
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _settings(tmp_path) -> WorkerSettings:
    return WorkerSettings(
        server_base_url="http://operator.test",
        worker_id="designer-laptop-01",
        worker_token="token",
        worker_temp_root=tmp_path,
        claude_cli_executable="claude",
        codex_cli_executable="codex",
        playwright_profile_root=tmp_path / "profiles",
        worker_capabilities=["agent.chat"],
    )


def _job(message: str, preferred_agent: str | None = None) -> JobForWorker:
    return JobForWorker(
        job_id="job_1",
        task_id="task_1",
        run_id="run_1",
        job_type=JobType.AGENT_CHAT,
        required_capability="agent.chat",
        action_name=AGENT_CHAT_ACTION,
        inputs={"message": message, "preferred_agent": preferred_agent, "context": {"mode": "chat"}},
        timeout_s=120,
        lease_ttl_s=90,
        lease_expires_at="2026-05-12T12:00:00+00:00",
        idempotency_key="job_1_attempt_1",
    )


def test_agent_chat_job_executor_returns_worker_completion_outputs(tmp_path) -> None:
    runtime = FakeRuntime(
        AgentCommandResult(agent="codex_cli", routed_to="codex_cli", text="open the browser and inspect it", raw_output="raw")
    )
    executor = AgentChatJobExecutor(_settings(tmp_path), runtime=runtime)

    outputs = executor.run(_job("please inspect the page", preferred_agent="codex_cli"))

    assert runtime.requests[0].message == "please inspect the page"
    assert runtime.requests[0].task_id == "task_1"
    assert runtime.requests[0].preferred_agent == "codex_cli"
    assert outputs["agent_chat"]["routed_to"] == "codex_cli"
    assert outputs["agent_chat"]["text"] == "open the browser and inspect it"


def test_default_worker_backends_do_not_include_operator_ollama() -> None:
    from creative_workflow.worker.agent_runtime.job_executor import _default_backends

    assert {backend.name for backend in _default_backends()} == {"claude_cli", "codex_cli"}


def test_agent_chat_job_executor_maps_runtime_failure_to_worker_failure(tmp_path) -> None:
    runtime = FakeRuntime(RuntimeError("Codex CLI is installed but not logged in."))
    executor = AgentChatJobExecutor(_settings(tmp_path), runtime=runtime)

    try:
        executor.run(_job("use browser"))
    except BrowserFlowError as exc:
        assert exc.failure_type == FailureType.DEPENDENCY_UNAVAILABLE
        assert "not logged in" in exc.message
    else:
        raise AssertionError("expected BrowserFlowError")
