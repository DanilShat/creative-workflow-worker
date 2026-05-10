"""Tool: list_artifacts — return artifact metadata + optional inline thumbnails."""

from __future__ import annotations

from typing import Any

from creative_workflow.worker.mcp.operator_client import OperatorClient
from creative_workflow.worker.mcp.schemas import (
    ArtifactSummary,
    ListArtifactsInput,
    ListArtifactsOutput,
)

_INLINE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


async def list_artifacts(
    payload: ListArtifactsInput,
    client: OperatorClient,
) -> tuple[ListArtifactsOutput, list[tuple[str, bytes, str]]]:
    """Return structured metadata plus any image bytes the server should
    render inline. The caller (server.py) is responsible for converting
    the (asset_id, bytes, mime) tuples into MCP image content blocks.
    """

    history = await client.get_task_history(payload.task_id)
    rows: list[dict[str, Any]] = list(history.get("assets", []))

    if payload.asset_class:
        rows = [r for r in rows if r.get("asset_class") == payload.asset_class]
    rows = rows[: payload.limit]

    summaries = [
        ArtifactSummary(
            asset_id=r["asset_id"],
            task_id=payload.task_id,
            asset_class=r.get("asset_class", "unknown"),
            content_type=r.get("content_type", "application/octet-stream"),
            filename=r.get("original_filename") or r.get("stored_filename", ""),
            size_bytes=int(r.get("size_bytes", 0)),
            download_url=f"{client._base_url}/api/v1/assets/{r['asset_id']}/download",
        )
        for r in rows
    ]

    inline_images: list[tuple[str, bytes, str]] = []
    if payload.inline_images:
        for s in summaries:
            if s.content_type in _INLINE_IMAGE_TYPES:
                try:
                    data, mime = await client.download_asset(s.asset_id)
                except Exception:
                    continue
                inline_images.append((s.asset_id, data, mime))

    return ListArtifactsOutput(task_id=payload.task_id, artifacts=summaries), inline_images
