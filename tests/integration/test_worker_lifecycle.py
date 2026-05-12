import json
from pathlib import Path

import httpx

from creative_workflow.shared.contracts.jobs import JobCompleteRequest
from creative_workflow.shared.contracts.workers import ClaimNextRequest, WorkerHeartbeatRequest, WorkerRegisterRequest
from creative_workflow.shared.enums import JobType, WorkerStatus
from creative_workflow.shared.time import iso_now
from creative_workflow.worker.config import WorkerSettings
from creative_workflow.worker.runtime.polling_client import PollingClient


def test_worker_protocol_lifecycle_with_mock_operator_api(tmp_path: Path):
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.headers["authorization"] == "Bearer test-token"
        payload = json.loads(request.content.decode())

        if request.url.path == "/api/v1/workers/register":
            assert payload["worker_id"] == "designer-laptop-01"
            return httpx.Response(
                200,
                json={
                    "worker_id": "designer-laptop-01",
                    "registered": True,
                    "server_time": iso_now(),
                    "heartbeat_interval_s": 15,
                    "claim_poll_interval_s": 3,
                    "active_job": None,
                },
            )

        if request.url.path == "/api/v1/workers/heartbeat":
            assert payload["status"] == WorkerStatus.IDLE.value
            return httpx.Response(200, json={"accepted": True, "server_time": iso_now(), "commands": []})

        if request.url.path == "/api/v1/workers/claim-next":
            return httpx.Response(
                200,
                json={
                    "job": {
                        "job_id": "job_1",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "job_type": JobType.BROWSER_FLOW.value,
                        "required_capability": "browser.gemini",
                        "action_name": "gemini_build_prompt_from_brief_and_refs",
                        "inputs": {"brief": "Create a clean product hero image."},
                        "input_assets": [],
                        "timeout_s": 1200,
                        "lease_ttl_s": 90,
                        "lease_expires_at": iso_now(),
                        "idempotency_key": "job_1:1",
                    },
                    "poll_after_s": 3,
                },
            )

        if request.url.path == "/api/v1/jobs/job_1/complete":
            assert payload["worker_id"] == "designer-laptop-01"
            assert payload["outputs"]["ok"] is True
            return httpx.Response(200, json={"accepted": True, "server_workflow_state": "waiting_human_review"})

        return httpx.Response(404, json={"error": request.url.path})

    settings = WorkerSettings(
        server_base_url="http://operator.test",
        worker_id="designer-laptop-01",
        worker_token="test-token",
        worker_temp_root=tmp_path / "temp",
        playwright_profile_root=tmp_path / "profiles",
        playwright_browser_channel=None,
        worker_capabilities=["browser.gemini"],
    )
    client = PollingClient(settings, transport=httpx.MockTransport(handler))

    registered = client.register(
        WorkerRegisterRequest(
            worker_id=settings.worker_id,
            version=settings.version,
            capabilities=settings.worker_capabilities,
        )
    )
    assert registered.registered is True

    heartbeat = client.heartbeat(
        WorkerHeartbeatRequest(
            worker_id=settings.worker_id,
            status=WorkerStatus.IDLE,
            capabilities=settings.worker_capabilities,
        )
    )
    assert heartbeat.accepted is True

    claim = client.claim_next(
        ClaimNextRequest(worker_id=settings.worker_id, capabilities=settings.worker_capabilities)
    )
    assert claim.job is not None
    assert claim.job.job_id == "job_1"

    completed = client.complete(
        "job_1",
        JobCompleteRequest(
            worker_id=settings.worker_id,
            outputs={"ok": True},
            completed_at=iso_now(),
        ),
    )
    assert completed["accepted"] is True
    assert seen_paths == [
        "/api/v1/workers/register",
        "/api/v1/workers/heartbeat",
        "/api/v1/workers/claim-next",
        "/api/v1/jobs/job_1/complete",
    ]


def test_worker_protocol_can_complete_agent_chat_job(tmp_path: Path):
    completed_payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        if request.url.path == "/api/v1/workers/register":
            assert "agent.chat" in payload["capabilities"]
            return httpx.Response(
                200,
                json={
                    "worker_id": "designer-laptop-01",
                    "registered": True,
                    "server_time": iso_now(),
                    "heartbeat_interval_s": 15,
                    "claim_poll_interval_s": 3,
                    "active_job": None,
                },
            )
        if request.url.path == "/api/v1/workers/heartbeat":
            return httpx.Response(200, json={"accepted": True, "server_time": iso_now(), "commands": []})
        if request.url.path == "/api/v1/workers/claim-next":
            assert "agent.chat" in payload["capabilities"]
            return httpx.Response(
                200,
                json={
                    "job": {
                        "job_id": "job_agent_1",
                        "task_id": "task_1",
                        "run_id": "run_1",
                        "job_type": JobType.AGENT_CHAT.value,
                        "required_capability": "agent.chat",
                        "action_name": "designer_agent_chat",
                        "inputs": {"message": "summarize task status"},
                        "input_assets": [],
                        "timeout_s": 600,
                        "lease_ttl_s": 90,
                        "lease_expires_at": iso_now(),
                        "idempotency_key": "job_agent_1:1",
                    },
                    "poll_after_s": 3,
                },
            )
        if request.url.path == "/api/v1/jobs/job_agent_1/complete":
            completed_payloads.append(payload)
            return httpx.Response(200, json={"accepted": True, "server_workflow_state": "agent_replied"})
        return httpx.Response(404, json={"error": request.url.path})

    settings = WorkerSettings(
        server_base_url="http://operator.test",
        worker_id="designer-laptop-01",
        worker_token="test-token",
        worker_temp_root=tmp_path / "temp",
        playwright_profile_root=tmp_path / "profiles",
        playwright_browser_channel=None,
        worker_capabilities=["agent.chat"],
    )
    client = PollingClient(settings, transport=httpx.MockTransport(handler))

    client.register(WorkerRegisterRequest(worker_id=settings.worker_id, version=settings.version, capabilities=settings.worker_capabilities))
    client.heartbeat(WorkerHeartbeatRequest(worker_id=settings.worker_id, status=WorkerStatus.IDLE, capabilities=settings.worker_capabilities))
    claim = client.claim_next(ClaimNextRequest(worker_id=settings.worker_id, capabilities=settings.worker_capabilities))
    assert claim.job is not None
    client.complete(
        claim.job.job_id,
        JobCompleteRequest(
            worker_id=settings.worker_id,
            outputs={"agent_chat": {"routed_to": "local_ollama", "text": "No active blockers."}},
            completed_at=iso_now(),
        ),
    )

    assert completed_payloads[0]["outputs"]["agent_chat"]["routed_to"] == "local_ollama"
