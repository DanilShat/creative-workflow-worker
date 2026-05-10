"""Integration tests for the MCP tools.

These exercise the tool functions directly against a mocked operator API
(via httpx.MockTransport) so we cover the contract without needing a
running server. The MCP framing layer (FastMCP) is exercised separately
when build_server() is called in test_mcp_server_build.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from creative_workflow.worker.config import WorkerSettings
from creative_workflow.worker.dcc.aftereffects_runner import (
    AERenderError,
    AERenderRequest,
    AERenderResult,
)
from creative_workflow.worker.mcp.server import build_server
from creative_workflow.worker.mcp.operator_client import OperatorClient
from creative_workflow.worker.mcp.schemas import (
    GetContextInput,
    ListArtifactsInput,
    RequestReviewInput,
    SubmitAfterEffectsRenderInput,
    SubmitBrowserJobInput,
)
from creative_workflow.worker.mcp.tools.get_context import get_context
from creative_workflow.worker.mcp.tools.list_artifacts import list_artifacts
from creative_workflow.worker.mcp.tools.request_review import request_review
from creative_workflow.worker.mcp.tools.submit_aftereffects_render import (
    submit_aftereffects_render,
)
from creative_workflow.worker.mcp.tools.submit_browser_job import submit_browser_job


def _settings(tmp_path: Path) -> WorkerSettings:
    env = tmp_path / ".env.worker"
    env.write_text(
        "SERVER_BASE_URL=http://operator.test\n"
        "WORKER_ID=designer-laptop-test\n"
        "WORKER_TOKEN=test-token\n",
        encoding="utf-8",
    )
    return WorkerSettings.load(env_file=env)


def _client_with_handler(
    settings: WorkerSettings,
    handler,
) -> OperatorClient:
    transport = httpx.MockTransport(handler)
    client = OperatorClient(settings)
    client._client = httpx.AsyncClient(
        base_url=settings.server_base_url,
        headers={"Authorization": f"Bearer {settings.worker_token}"},
        transport=transport,
    )
    return client


def test_mcp_server_registers_aftereffects_render_tool(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    server = build_server(settings)

    assert "submit_aftereffects_render" in server._tool_manager._tools


@pytest.mark.asyncio
async def test_get_context_returns_brief_and_jobs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"
        assert request.url.path == "/api/v1/tasks/task_1/history"
        return httpx.Response(
            200,
            json={
                "task": {"title": "Spring drop hero", "brief": "Soft pastels."},
                "jobs": [
                    {
                        "job_id": "job_1",
                        "job_type": "browser_flow",
                        "action_name": "gemini_generate",
                        "status": "succeeded",
                    }
                ],
                "assets": [{"asset_id": "a1"}, {"asset_id": "a2"}],
            },
        )

    async with _client_with_handler(settings, handler) as client:
        result = await get_context(GetContextInput(task_id="task_1"), client)

    assert result.title == "Spring drop hero"
    assert len(result.jobs) == 1
    assert result.jobs[0].job_id == "job_1"
    assert result.artifact_count == 2


@pytest.mark.asyncio
async def test_list_artifacts_inlines_image_bytes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    fake_png = b"\x89PNG\r\n\x1a\nfakebody"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/tasks/task_1/history":
            return httpx.Response(
                200,
                json={
                    "task": {},
                    "jobs": [],
                    "assets": [
                        {
                            "asset_id": "a1",
                            "asset_class": "generated",
                            "content_type": "image/png",
                            "original_filename": "hero_01.png",
                            "size_bytes": len(fake_png),
                        }
                    ],
                },
            )
        if request.url.path == "/api/v1/assets/a1/download":
            return httpx.Response(
                200,
                content=fake_png,
                headers={"content-type": "image/png"},
            )
        return httpx.Response(404)

    async with _client_with_handler(settings, handler) as client:
        output, inline = await list_artifacts(
            ListArtifactsInput(task_id="task_1"), client
        )

    assert len(output.artifacts) == 1
    assert output.artifacts[0].content_type == "image/png"
    assert len(inline) == 1
    assert inline[0][1] == fake_png
    assert inline[0][2] == "image/png"


@pytest.mark.asyncio
async def test_request_review_posts_decision(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"ok": True})

    async with _client_with_handler(settings, handler) as client:
        result = await request_review(
            RequestReviewInput(
                task_id="task_1",
                run_id="run_1",
                decision="approved",
                selected_asset_id="a1",
                reason="this one is the cleanest",
            ),
            client,
        )

    assert captured["path"] == "/api/v1/tasks/task_1/reviews"
    assert captured["body"]["decision"] == "approved"
    assert captured["body"]["selected_asset_id"] == "a1"
    assert result.decision == "approved"


@pytest.mark.asyncio
async def test_submit_browser_job_creates_task_and_fans_variants(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/tasks":
            captured["create"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "task_id": "task_new",
                    "workflow_state": "draft",
                    "created_at": "2026-05-10T10:00:00+00:00",
                },
            )
        if (
            request.method == "POST"
            and request.url.path == "/api/v1/tasks/task_new/start-gate-a"
        ):
            captured["start"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "task_id": "task_new",
                    "run_id": "run_1",
                    "workflow_state": "waiting_worker",
                    "created_job_ids": [f"job_{i}" for i in range(8)],
                },
            )
        return httpx.Response(404)

    async with _client_with_handler(settings, handler) as client:
        result = await submit_browser_job(
            SubmitBrowserJobInput(
                title="Spring drop hero",
                brief="Soft pastels, airy.",
                variant_count=8,
            ),
            client,
        )

    assert captured["create"]["title"] == "Spring drop hero"
    assert captured["start"]["variant_count"] == 8
    assert result.task_id == "task_new"
    assert result.run_id == "run_1"
    assert len(result.job_ids) == 8


@pytest.mark.asyncio
async def test_submit_browser_job_explains_missing_references(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/api/v1/tasks":
            return httpx.Response(
                200,
                json={
                    "task_id": "task_new",
                    "workflow_state": "draft",
                    "created_at": "2026-05-10T10:00:00+00:00",
                },
            )
        if request.url.path.endswith("/start-gate-a"):
            return httpx.Response(
                409,
                json={
                    "detail": {
                        "code": "conflict",
                        "message": "Gate A requires at least one reference asset.",
                    }
                },
            )
        return httpx.Response(404)

    async with _client_with_handler(settings, handler) as client:
        result = await submit_browser_job(
            SubmitBrowserJobInput(
                title="Spring drop hero",
                brief="Soft pastels, airy.",
                variant_count=4,
            ),
            client,
        )

    assert result.workflow_state == "blocked"
    assert result.note is not None
    assert "reference" in result.note.lower()


@pytest.mark.asyncio
async def test_submit_aftereffects_render_invokes_aerender(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "template.aep"
    output = tmp_path / "renders" / "spot.mov"
    project.write_bytes(b"fake-aep")
    captured: dict[str, AERenderRequest] = {}

    async def fake_run(req: AERenderRequest) -> AERenderResult:
        captured["req"] = req
        return AERenderResult(
            output_path=req.output_path,
            duration_s=1.234,
            stdout_tail="ok",
            stderr_tail="",
        )

    monkeypatch.setattr(
        "creative_workflow.worker.mcp.tools.submit_aftereffects_render.run_aerender",
        fake_run,
    )

    result = await submit_aftereffects_render(
        SubmitAfterEffectsRenderInput(
            project_path=str(project),
            comp_name="Main_9x16",
            output_path=str(output),
            output_module="H.264",
        )
    )

    assert captured["req"].project_path == project
    assert captured["req"].comp_name == "Main_9x16"
    assert captured["req"].output_path == output
    assert captured["req"].output_module == "H.264"
    assert result.error is None
    assert result.duration_s == 1.23
    assert result.output_path == str(output)


@pytest.mark.asyncio
async def test_submit_aftereffects_render_returns_actionable_error(monkeypatch, tmp_path: Path) -> None:
    async def fake_run(_req: AERenderRequest) -> AERenderResult:
        raise AERenderError("Could not locate aerender.exe. Set AERENDER_EXE.")

    monkeypatch.setattr(
        "creative_workflow.worker.mcp.tools.submit_aftereffects_render.run_aerender",
        fake_run,
    )

    result = await submit_aftereffects_render(
        SubmitAfterEffectsRenderInput(
            project_path=str(tmp_path / "missing.aep"),
            comp_name="Main_9x16",
            output_path=str(tmp_path / "renders" / "spot.mov"),
        )
    )

    assert result.duration_s == 0.0
    assert result.error is not None
    assert "AERENDER_EXE" in result.error
