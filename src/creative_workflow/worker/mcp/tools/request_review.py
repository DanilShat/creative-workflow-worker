"""Tool: request_review — submit an approve/reject decision back to the operator."""

from __future__ import annotations

from datetime import datetime, timezone

from creative_workflow.worker.mcp.operator_client import OperatorClient
from creative_workflow.worker.mcp.schemas import (
    RequestReviewInput,
    RequestReviewOutput,
)


async def request_review(
    payload: RequestReviewInput,
    client: OperatorClient,
) -> RequestReviewOutput:
    await client.submit_review(
        payload.task_id,
        run_id=payload.run_id,
        decision=payload.decision,
        selected_asset_id=payload.selected_asset_id,
        reason=payload.reason,
    )
    return RequestReviewOutput(
        task_id=payload.task_id,
        run_id=payload.run_id,
        decision=payload.decision,
        submitted_at=datetime.now(tz=timezone.utc),
    )
