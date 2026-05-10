"""Tool: submit_browser_job — create a task (or reuse one) and fan out N variants."""

from __future__ import annotations

import httpx

from creative_workflow.worker.mcp.operator_client import OperatorClient
from creative_workflow.worker.mcp.schemas import (
    SubmitBrowserJobInput,
    SubmitBrowserJobOutput,
)


_REFERENCES_REQUIRED = (
    "Gate A requires at least one reference asset. Open the operator "
    "Streamlit UI for this task and upload a reference image, then ask me "
    "to retry."
)


async def submit_browser_job(
    payload: SubmitBrowserJobInput,
    client: OperatorClient,
) -> SubmitBrowserJobOutput:
    if payload.existing_task_id:
        task_id = payload.existing_task_id
    else:
        created = await client.create_task(
            title=payload.title,
            brief_text=payload.brief,
            requested_output_type=payload.requested_output_type,
            created_by="designer",
        )
        task_id = created["task_id"]

    try:
        result = await client.start_gate_a(
            task_id,
            operator_note=None,
            variant_count=payload.variant_count,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 409:
            return SubmitBrowserJobOutput(
                task_id=task_id,
                run_id="",
                job_ids=[],
                workflow_state="blocked",
                variant_count=payload.variant_count,
                note=_REFERENCES_REQUIRED,
            )
        raise

    return SubmitBrowserJobOutput(
        task_id=task_id,
        run_id=result["run_id"],
        job_ids=list(result.get("created_job_ids", [])),
        workflow_state=result.get("workflow_state", "waiting_worker"),
        variant_count=payload.variant_count,
    )
