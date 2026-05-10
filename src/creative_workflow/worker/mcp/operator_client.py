"""HTTP client used by the MCP server to query the operator API.

Kept separate from `runtime.polling_client.PollingClient` because that
client is the worker daemon's claim/heartbeat path and should not grow
read-side or designer-facing methods.
"""

from __future__ import annotations

from typing import Any

import httpx

from creative_workflow.worker.config import WorkerSettings


class OperatorClient:
    def __init__(self, settings: WorkerSettings, *, timeout_s: float = 15.0) -> None:
        self._base_url = settings.server_base_url
        self._headers = {"Authorization": f"Bearer {settings.worker_token}"}
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=timeout_s,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OperatorClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def get_task(self, task_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/api/v1/tasks/{task_id}")
        resp.raise_for_status()
        return resp.json()

    async def create_task(
        self,
        *,
        title: str,
        brief_text: str,
        requested_output_type: str = "static_image",
        created_by: str = "designer",
    ) -> dict[str, Any]:
        resp = await self._client.post(
            "/api/v1/tasks",
            json={
                "title": title,
                "brief_text": brief_text,
                "requested_output_type": requested_output_type,
                "created_by": created_by,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def start_gate_a(
        self,
        task_id: str,
        *,
        operator_note: str | None = None,
        variant_count: int = 1,
    ) -> dict[str, Any]:
        resp = await self._client.post(
            f"/api/v1/tasks/{task_id}/start-gate-a",
            json={
                "task_id": task_id,
                "operator_note": operator_note,
                "variant_count": variant_count,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def get_task_history(self, task_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/api/v1/tasks/{task_id}/history")
        resp.raise_for_status()
        return resp.json()

    async def submit_review(
        self,
        task_id: str,
        *,
        run_id: str,
        decision: str,
        selected_asset_id: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        payload = {
            "run_id": run_id,
            "decision": decision,
            "selected_asset_id": selected_asset_id,
            "reason": reason,
        }
        resp = await self._client.post(
            f"/api/v1/tasks/{task_id}/reviews",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def download_asset(self, asset_id: str) -> tuple[bytes, str]:
        resp = await self._client.get(f"/api/v1/assets/{asset_id}/download")
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "application/octet-stream")
        return resp.content, content_type
