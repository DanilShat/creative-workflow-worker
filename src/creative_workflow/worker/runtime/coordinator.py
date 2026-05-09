"""Main worker coordinator.

The coordinator enforces the MVP invariant of one active job at a time. A
background heartbeat keeps the server lease alive while long browser generation
jobs run.
"""

from collections.abc import Callable
from pathlib import Path
import socket
import threading
import time
import traceback

import httpx

from creative_workflow.shared.contracts.jobs import JobCompleteRequest, JobFailRequest, JobProgressRequest
from creative_workflow.shared.contracts.workers import (
    ClaimNextRequest,
    JobForWorker,
    WorkerHeartbeatRequest,
    WorkerRegisterRequest,
)
from creative_workflow.shared.enums import FailureType, JobExecutionState, WorkerStatus
from creative_workflow.shared.time import iso_now
from creative_workflow.worker.assets.manager import WorkerAssetManager
from creative_workflow.worker.browser.flows import FLOW_CLASSES
from creative_workflow.worker.browser.flows.base import BrowserFlowError
from creative_workflow.worker.browser.profiles import ProfileManager
from creative_workflow.worker.config import WorkerSettings
from creative_workflow.worker.runtime.polling_client import PollingClient
from creative_workflow.worker.runtime.state import LocalStateStore, WorkerLocalState


class WorkerCoordinator:
    def __init__(self, settings: WorkerSettings):
        self.settings = settings
        self.client = PollingClient(settings)
        self.profiles = ProfileManager(settings.playwright_profile_root)
        self.assets = WorkerAssetManager(settings.worker_temp_root, self.client)
        self.state_store = LocalStateStore(settings.worker_temp_root / "worker_state.json")
        self.state = self.state_store.load(settings.worker_id)
        self.stop_event = threading.Event()
        self.heartbeat_interval_s = 15
        self.claim_poll_interval_s = 3

    def register(self) -> None:
        self.state.status = "registering"
        self._save_state()
        print(f"[worker] registering {self.settings.worker_id} at {self.settings.server_base_url}", flush=True)
        response = self.client.register(
            WorkerRegisterRequest(
                worker_id=self.settings.worker_id,
                display_name=socket.gethostname(),
                version=self.settings.version,
                capabilities=self.settings.worker_capabilities,
                host_apps={
                    "photoshop": {"installed": False, "connected": False, "version": None},
                    "aftereffects": {"installed": False, "connected": False, "version": None},
                },
                profiles={service: {"status": status} for service, status in self.profiles.list_profiles().items()},
                machine_info={"hostname": socket.gethostname(), "os": "windows", "user_session_active": True},
            )
        )
        self.heartbeat_interval_s = response.heartbeat_interval_s
        self.claim_poll_interval_s = response.claim_poll_interval_s
        # A worker can be killed while a browser job is running. On restart the
        # local diagnostic state file may still contain that old active_job_id.
        # The server remains authoritative; use the server's registration
        # response instead of replaying stale local state.
        self.state.active_job_id = response.active_job
        self.state.status = "idle"
        self._save_state()
        print(
            f"[worker] registered; heartbeat={self.heartbeat_interval_s}s poll={self.claim_poll_interval_s}s",
            flush=True,
        )

    def run_forever(self) -> None:
        self.settings.worker_temp_root.mkdir(parents=True, exist_ok=True)
        self.register()
        heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat.start()
        while not self.stop_event.is_set():
            try:
                self._claim_and_execute_once()
            except httpx.HTTPError as exc:
                print(f"Worker protocol error: {exc}")
                time.sleep(self.claim_poll_interval_s)
            except Exception:
                print(traceback.format_exc())
                time.sleep(self.claim_poll_interval_s)

    def stop(self) -> None:
        self.stop_event.set()

    def _heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.client.heartbeat(
                    WorkerHeartbeatRequest(
                        worker_id=self.settings.worker_id,
                        status=WorkerStatus.RUNNING if self.state.active_job_id else WorkerStatus.IDLE,
                        active_job_id=self.state.active_job_id,
                        capabilities=self.settings.worker_capabilities,
                        profile_status={service: status for service, status in self.profiles.list_profiles().items()},
                        host_app_status={"photoshop": "unavailable", "aftereffects": "unavailable"},
                        health={"temp_root": str(self.settings.worker_temp_root), "browser_runtime_ok": True},
                    )
                )
            except Exception as exc:
                print(f"Heartbeat failed: {exc}")
            self.stop_event.wait(self.heartbeat_interval_s)

    def _claim_and_execute_once(self) -> None:
        claim = self.client.claim_next(
            ClaimNextRequest(
                worker_id=self.settings.worker_id,
                capabilities=self.settings.worker_capabilities,
                active_job_id=self.state.active_job_id,
            )
        )
        if claim.job is None:
            self.stop_event.wait(claim.poll_after_s)
            return
        print(f"[worker] claimed {claim.job.job_id}: {claim.job.action_name}", flush=True)
        self.state.active_job_id = claim.job.job_id
        self.state.status = "running"
        self._save_state()
        try:
            self._execute_job(claim.job)
        finally:
            self.state.active_job_id = None
            self.state.status = "idle"
            self._save_state()

    def _execute_job(self, job: JobForWorker) -> None:
        print(f"[worker] {job.job_id} downloading inputs", flush=True)
        self._progress(job, JobExecutionState.PREPARING_INPUTS, "download_inputs", "Downloading input assets")
        input_paths = self.assets.download_inputs(job.job_id, job.input_assets)
        print(f"[worker] {job.job_id} executing {job.action_name}", flush=True)
        self._progress(job, JobExecutionState.EXECUTING, "execute_flow", f"Executing {job.action_name}")
        try:
            flow_class = FLOW_CLASSES.get(job.action_name)
            if flow_class is None:
                raise BrowserFlowError(FailureType.UNSUPPORTED_ACTION_NAME, f"Unsupported worker action {job.action_name}")
            result = flow_class(self.profiles, self.assets).run(job, input_paths)
            print(f"[worker] {job.job_id} uploading completion", flush=True)
            self._progress(job, JobExecutionState.UPLOADING_ARTIFACTS, "complete", "Reporting job completion")
            all_artifacts = result.artifact_ids + result.debug_asset_ids
            self.client.complete(
                job.job_id,
                JobCompleteRequest(
                    worker_id=self.settings.worker_id,
                    outputs={"flow_result": result.flow_result, "structured_output": result.flow_result.get("structured_output", {})},
                    artifact_ids=all_artifacts,
                    completed_at=iso_now(),
                ),
            )
        except BrowserFlowError as exc:
            print(f"[worker] {job.job_id} failed: {exc.failure_type.value}: {exc.message}", flush=True)
            self.client.fail(
                job.job_id,
                JobFailRequest(
                    worker_id=self.settings.worker_id,
                    failure_type=exc.failure_type,
                    retryable=exc.failure_type
                    in {
                        FailureType.NETWORK_TEMPORARY,
                        FailureType.UPLOAD_FAILED,
                        FailureType.DOWNLOAD_FAILED,
                        FailureType.TRANSIENT_BROWSER_START_FAILURE,
                    },
                    message=exc.message,
                    debug_asset_ids=[],
                    failed_at=iso_now(),
                ),
            )

    def _progress(self, job: JobForWorker, state: JobExecutionState, step: str, message: str) -> None:
        self.client.progress(
            job.job_id,
            JobProgressRequest(
                worker_id=self.settings.worker_id,
                state=state,
                step=step,
                message=message,
                timestamp=iso_now(),
            ),
        )

    def _save_state(self) -> None:
        self.state.worker_id = self.settings.worker_id
        self.state.capabilities = self.settings.worker_capabilities
        self.state_store.save(self.state)
