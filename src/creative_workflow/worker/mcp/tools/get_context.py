"""Tool: get_context — fetch task brief, jobs, and artifact count."""

from __future__ import annotations

from creative_workflow.worker.mcp.operator_client import OperatorClient
from creative_workflow.worker.mcp.schemas import (
    GetContextInput,
    GetContextOutput,
    JobSummary,
)


async def get_context(
    payload: GetContextInput,
    client: OperatorClient,
) -> GetContextOutput:
    history = await client.get_task_history(payload.task_id)
    task = history.get("task", {})

    jobs = [
        JobSummary(
            job_id=j["job_id"],
            task_id=payload.task_id,
            job_type=j.get("job_type", ""),
            action_name=j.get("action_name", ""),
            status=j.get("status", "pending"),
            started_at=j.get("started_at"),
            finished_at=j.get("finished_at"),
        )
        for j in history.get("jobs", [])
    ]

    return GetContextOutput(
        task_id=payload.task_id,
        title=task.get("title"),
        brief=task.get("brief"),
        jobs=jobs,
        artifact_count=len(history.get("assets", [])),
    )
