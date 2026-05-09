"""Base classes for live Playwright browser flows.

Browser flows are allowlisted by action name. They launch persistent profiles,
produce structured results, and preserve debug artifacts instead of returning
silent success.
"""

from dataclasses import dataclass, field
from pathlib import Path
import json

from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import AssetClass, DebugKind, FailureType, RetentionClass, SourceService
from creative_workflow.worker.assets.manager import WorkerAssetManager
from creative_workflow.worker.browser.profiles import ProfileManager


@dataclass
class FlowExecutionResult:
    flow_result: dict
    artifact_ids: list[str] = field(default_factory=list)
    debug_asset_ids: list[str] = field(default_factory=list)


class BrowserFlowError(Exception):
    def __init__(self, failure_type: FailureType, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.message = message


class BaseBrowserFlow:
    service: SourceService
    flow_name: str

    def __init__(self, profiles: ProfileManager, assets: WorkerAssetManager):
        self.profiles = profiles
        self.assets = assets

    def _write_step_log(self, job_dir: Path, steps: list[dict]) -> Path:
        path = job_dir / "debug" / "step_log.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(steps, indent=2), encoding="utf-8")
        return path

    def _upload_step_log(self, path: Path, job: JobForWorker) -> str:
        return self.assets.upload_artifact(
            path,
            task_id=job.task_id,
            run_id=job.run_id,
            job_id=job.job_id,
            asset_class=AssetClass.DEBUG,
            retention_class=RetentionClass.DEBUG_TTL_7D,
            source_service=self.service,
            content_type="application/json",
            debug_kind=DebugKind.STEP_LOG,
        )

