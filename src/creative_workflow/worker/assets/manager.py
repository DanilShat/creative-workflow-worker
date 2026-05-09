"""Worker-side asset download/upload manager."""

from pathlib import Path
import hashlib
import re

from creative_workflow.shared.contracts.assets import AssetUploadMetadata, JobInputAsset
from creative_workflow.shared.enums import AssetClass, DebugKind, RetentionClass, SourceService
from creative_workflow.worker.runtime.polling_client import PollingClient


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name) or "asset.bin"


class WorkerAssetManager:
    def __init__(self, temp_root: Path, client: PollingClient):
        self.temp_root = temp_root
        self.client = client

    def prepare_job_dir(self, job_id: str) -> Path:
        path = self.temp_root / "jobs" / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def download_inputs(self, job_id: str, input_assets: list[JobInputAsset]) -> dict[str, Path]:
        job_dir = self.prepare_job_dir(job_id)
        result: dict[str, Path] = {}
        for asset in input_assets:
            data = self.client.download(asset.download_url)
            actual = hashlib.sha256(data).hexdigest()
            if actual.lower() != asset.sha256.lower():
                raise ValueError(f"Checksum mismatch for input asset {asset.asset_id}.")
            path = job_dir / "inputs" / f"{asset.asset_id}_{_safe_name(asset.filename)}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            result[asset.asset_id] = path
        return result

    def upload_artifact(
        self,
        path: Path,
        task_id: str,
        run_id: str,
        job_id: str,
        asset_class: AssetClass,
        retention_class: RetentionClass,
        source_service: SourceService,
        content_type: str,
        debug_kind: DebugKind | None = None,
    ) -> str:
        metadata = AssetUploadMetadata(
            task_id=task_id,
            run_id=run_id,
            job_id=job_id,
            asset_class=asset_class,
            retention_class=retention_class,
            original_filename=path.name,
            content_type=content_type,
            size_bytes=path.stat().st_size,
            sha256=sha256_file(path),
            source_service=source_service,
            debug_kind=debug_kind,
        )
        return self.client.upload(path, metadata).asset_id

