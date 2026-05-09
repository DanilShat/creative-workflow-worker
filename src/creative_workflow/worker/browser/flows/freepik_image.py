"""Live Freepik browser image generation flow."""

from pathlib import Path
import mimetypes
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from creative_workflow.shared.contracts.jobs import BrowserFlowResult, FreepikGenerationOutput
from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import AssetClass, DebugKind, FailureType, ProfileStatus, RetentionClass, SourceService
from creative_workflow.worker.browser.flows.base import BaseBrowserFlow, BrowserFlowError, FlowExecutionResult
from creative_workflow.worker.browser.launch import persistent_context_options
from creative_workflow.worker.browser.profiles import SERVICE_URLS


class FreepikImageFlow(BaseBrowserFlow):
    service = SourceService.FREEPIK
    flow_name = "freepik_generate_image_from_prompt"

    def run(self, job: JobForWorker, input_paths: dict[str, Path]) -> FlowExecutionResult:
        job_dir = self.assets.prepare_job_dir(job.job_id)
        download_dir = job_dir / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = job_dir / "debug" / "freepik_final.png"
        steps: list[dict] = []
        downloaded: list[Path] = []
        try:
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(
                    **persistent_context_options(self.profiles.profile_dir("freepik")),
                )
                page = context.new_page()
                steps.append({"step": "open_service"})
                page.goto(SERVICE_URLS["freepik"], wait_until="domcontentloaded", timeout=60000)
                status = self.profiles.validate_open_page("freepik", page)
                self.profiles.save_status("freepik", status)
                if status not in {ProfileStatus.AUTHENTICATED, ProfileStatus.UNKNOWN}:
                    raise BrowserFlowError(FailureType.NEEDS_REAUTH, f"Freepik profile status is {status.value}.")

                prompt = job.inputs.get("prompt", "")
                if not prompt:
                    raise BrowserFlowError(FailureType.INVALID_JOB_PAYLOAD, "Freepik job requires prompt.")
                steps.append({"step": "fill_prompt"})
                prompt_box = page.locator("textarea, [contenteditable='true'], input[type='text']").first
                prompt_box.wait_for(timeout=30000)
                prompt_box.fill(prompt)

                steps.append({"step": "submit_generation"})
                try:
                    page.get_by_role("button", name=re.compile("generate|create", re.I)).click(timeout=15000)
                except PlaywrightTimeoutError as exc:
                    raise BrowserFlowError(FailureType.SELECTOR_BROKEN, "Could not find Freepik generate button.") from exc

                steps.append({"step": "wait_for_result"})
                page.get_by_text(re.compile("download|export", re.I)).first.wait_for(timeout=job.timeout_s * 1000)
                page.screenshot(path=str(screenshot_path), full_page=True)

                steps.append({"step": "download_outputs"})
                with page.expect_download(timeout=120000) as download_info:
                    page.get_by_text(re.compile("download", re.I)).first.click()
                download = download_info.value
                target = download_dir / download.suggested_filename
                download.save_as(str(target))
                downloaded.append(target)
                context.close()
        except BrowserFlowError:
            raise
        except Exception as exc:
            raise BrowserFlowError(FailureType.SELECTOR_BROKEN, f"Freepik flow failed: {exc}") from exc

        generated_ids: list[str] = []
        for path in downloaded:
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            generated_ids.append(
                self.assets.upload_artifact(
                    path,
                    task_id=job.task_id,
                    run_id=job.run_id,
                    job_id=job.job_id,
                    asset_class=AssetClass.GENERATED,
                    retention_class=RetentionClass.TTL_30D,
                    source_service=SourceService.FREEPIK,
                    content_type=content_type,
                )
            )
        screenshot_id = self.assets.upload_artifact(
            screenshot_path,
            task_id=job.task_id,
            run_id=job.run_id,
            job_id=job.job_id,
            asset_class=AssetClass.DEBUG,
            retention_class=RetentionClass.DEBUG_TTL_7D,
            source_service=SourceService.FREEPIK,
            content_type="image/png",
            debug_kind=DebugKind.SCREENSHOT,
        )
        step_log_id = self._upload_step_log(self._write_step_log(job_dir, steps), job)
        structured = FreepikGenerationOutput(
            generated_asset_ids=generated_ids,
            selected_asset_id=generated_ids[0] if generated_ids else None,
            downloaded_files_count=len(downloaded),
        )
        flow = BrowserFlowResult(
            service=SourceService.FREEPIK,
            flow_name=self.flow_name,
            profile_status=ProfileStatus.AUTHENTICATED,
            structured_output=structured.model_dump(),
            artifact_ids=generated_ids,
            debug_asset_ids=[screenshot_id, step_log_id],
            external_urls=[],
        )
        return FlowExecutionResult(flow_result=flow.model_dump(mode="json"), artifact_ids=generated_ids, debug_asset_ids=[screenshot_id, step_log_id])
