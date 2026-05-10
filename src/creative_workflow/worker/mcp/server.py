"""FastMCP server entry point.

Run with `creative-workflow-mcp` (registered as a project script) or
`python -m creative_workflow.worker.mcp.server`. Claude Desktop spawns
this process over stdio.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image

from creative_workflow.worker.config import WorkerSettings
from creative_workflow.worker.mcp.operator_client import OperatorClient
from creative_workflow.worker.mcp.prompts import register_prompts
from creative_workflow.worker.mcp.schemas import (
    GetContextInput,
    ListArtifactsInput,
    RequestReviewInput,
    SubmitAfterEffectsRenderInput,
    SubmitBrowserJobInput,
)
from creative_workflow.worker.mcp.tools.get_context import get_context as do_get_context
from creative_workflow.worker.mcp.tools.list_artifacts import (
    list_artifacts as do_list_artifacts,
)
from creative_workflow.worker.mcp.tools.request_review import (
    request_review as do_request_review,
)
from creative_workflow.worker.mcp.tools.submit_aftereffects_render import (
    submit_aftereffects_render as do_submit_ae_render,
)
from creative_workflow.worker.mcp.tools.submit_browser_job import (
    submit_browser_job as do_submit_browser_job,
)


def build_server(settings: WorkerSettings | None = None) -> FastMCP:
    """Build the FastMCP server with all tools and prompts registered.

    Settings are loaded once at server start. Each tool call opens a fresh
    OperatorClient so a long-lived chat session doesn't keep an idle
    connection pinned.
    """

    cfg = settings or WorkerSettings.load()
    errors = cfg.validate()
    if errors:
        raise RuntimeError("Worker config invalid: " + "; ".join(errors))

    mcp = FastMCP(
        "creative-workflow",
        instructions=(
            "Tools for the designer's creative workflow. Use `get_context` "
            "to see the brief and recent jobs for a task, `list_artifacts` to "
            "view generated assets (image thumbnails render inline), and "
            "`request_review` to record an approve/reject decision."
        ),
    )

    @mcp.tool(description="Fetch the brief, jobs, and artifact count for a task.")
    async def get_context(task_id: str) -> str:
        async with OperatorClient(cfg) as client:
            result = await do_get_context(GetContextInput(task_id=task_id), client)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        description=(
            "List artifacts for a task. Image artifacts are rendered inline "
            "as thumbnails in the chat unless `inline_images` is false."
        )
    )
    async def list_artifacts(
        task_id: str,
        asset_class: str | None = None,
        inline_images: bool = True,
        limit: int = 20,
    ) -> list[Any]:
        payload = ListArtifactsInput(
            task_id=task_id,
            asset_class=asset_class,
            inline_images=inline_images,
            limit=limit,
        )
        async with OperatorClient(cfg) as client:
            output, inlined = await do_list_artifacts(payload, client)

        blocks: list[Any] = [output.model_dump_json(indent=2)]
        for _asset_id, data, mime in inlined:
            fmt = mime.split("/")[-1] if "/" in mime else "png"
            blocks.append(Image(data=data, format=fmt))
        return blocks

    @mcp.tool(
        description=(
            "Submit an approve or reject decision for a run. `decision` must "
            "be 'approved' or 'rejected'. `selected_asset_id` identifies the "
            "winning artifact when approving a variant set."
        )
    )
    async def request_review(
        task_id: str,
        run_id: str,
        decision: str,
        selected_asset_id: str | None = None,
        reason: str | None = None,
    ) -> str:
        payload = RequestReviewInput(
            task_id=task_id,
            run_id=run_id,
            decision=decision,  # type: ignore[arg-type]
            selected_asset_id=selected_asset_id,
            reason=reason,
        )
        async with OperatorClient(cfg) as client:
            result = await do_request_review(payload, client)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        description=(
            "Kick off a creative job. Either creates a new task with a brief "
            "or fans out variants on an existing task_id. Returns task_id, "
            "run_id, and the list of job_ids that were queued. Designer must "
            "have uploaded at least one reference asset before calling; if "
            "not, the response will explain how to fix it."
        )
    )
    async def submit_browser_job(
        title: str,
        brief: str,
        variant_count: int = 8,
        existing_task_id: str | None = None,
        requested_output_type: str = "static_image",
    ) -> str:
        payload = SubmitBrowserJobInput(
            title=title,
            brief=brief,
            variant_count=variant_count,
            existing_task_id=existing_task_id,
            requested_output_type=requested_output_type,
        )
        async with OperatorClient(cfg) as client:
            result = await do_submit_browser_job(payload, client)
        return result.model_dump_json(indent=2)

    @mcp.tool(
        description=(
            "Render a named comp from an After Effects project using the "
            "designer laptop's local aerender.exe. Requires After Effects "
            "to be installed and AERENDER_EXE set if aerender is not on PATH."
        )
    )
    async def submit_aftereffects_render(
        project_path: str,
        comp_name: str,
        output_path: str,
        output_module: str = "Lossless",
    ) -> str:
        payload = SubmitAfterEffectsRenderInput(
            project_path=project_path,
            comp_name=comp_name,
            output_path=output_path,
            output_module=output_module,
        )
        result = await do_submit_ae_render(payload)
        return result.model_dump_json(indent=2)

    register_prompts(mcp)
    return mcp


def run() -> None:
    """Console-script entry point for `creative-workflow-mcp`."""
    server = build_server()
    server.run()


if __name__ == "__main__":  # pragma: no cover
    run()
