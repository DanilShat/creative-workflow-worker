"""HTTP client for the worker polling protocol."""

from pathlib import Path
from typing import Any

import httpx

from creative_workflow.shared.contracts.assets import AssetUploadMetadata, AssetUploadResponse
from creative_workflow.shared.contracts.jobs import JobCompleteRequest, JobFailRequest, JobProgressRequest
from creative_workflow.shared.contracts.workers import (
    ClaimNextRequest,
    ClaimNextResponse,
    WorkerHeartbeatRequest,
    WorkerHeartbeatResponse,
    WorkerRegisterRequest,
    WorkerRegisterResponse,
)
from creative_workflow.worker.config import WorkerSettings


class PollingClient:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings
        self.client = httpx.Client(
            base_url=settings.server_base_url,
            timeout=60,
            headers={"Authorization": f"Bearer {settings.worker_token}"},
        )

    def register(self, payload: WorkerRegisterRequest) -> WorkerRegisterResponse:
        response = self.client.post("/api/v1/workers/register", json=payload.model_dump(mode="json"))
        response.raise_for_status()
        return WorkerRegisterResponse.model_validate(response.json())

    def heartbeat(self, payload: WorkerHeartbeatRequest) -> WorkerHeartbeatResponse:
        response = self.client.post("/api/v1/workers/heartbeat", json=payload.model_dump(mode="json"))
        response.raise_for_status()
        return WorkerHeartbeatResponse.model_validate(response.json())

    def claim_next(self, payload: ClaimNextRequest) -> ClaimNextResponse:
        response = self.client.post("/api/v1/workers/claim-next", json=payload.model_dump(mode="json"))
        response.raise_for_status()
        return ClaimNextResponse.model_validate(response.json())

    def progress(self, job_id: str, payload: JobProgressRequest) -> None:
        response = self.client.post(f"/api/v1/jobs/{job_id}/progress", json=payload.model_dump(mode="json"))
        response.raise_for_status()

    def complete(self, job_id: str, payload: JobCompleteRequest) -> dict[str, Any]:
        response = self.client.post(f"/api/v1/jobs/{job_id}/complete", json=payload.model_dump(mode="json"))
        response.raise_for_status()
        return response.json()

    def fail(self, job_id: str, payload: JobFailRequest) -> dict[str, Any]:
        response = self.client.post(f"/api/v1/jobs/{job_id}/fail", json=payload.model_dump(mode="json"))
        response.raise_for_status()
        return response.json()

    def download(self, download_url: str) -> bytes:
        response = self.client.get(download_url)
        response.raise_for_status()
        return response.content

    def upload(self, path: Path, metadata: AssetUploadMetadata) -> AssetUploadResponse:
        with path.open("rb") as handle:
            response = self.client.post(
                "/api/v1/assets/upload",
                files={"file": (metadata.original_filename, handle, metadata.content_type)},
                data={"metadata": metadata.model_dump_json()},
            )
        response.raise_for_status()
        return AssetUploadResponse.model_validate(response.json())

