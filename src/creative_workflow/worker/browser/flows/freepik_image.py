"""Freepik image generation flow powered by Claude Code CLI desktop-browser mode."""

from pathlib import Path
import json
import mimetypes

from creative_workflow.shared.contracts.jobs import BrowserFlowResult, FreepikGenerationOutput
from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import AssetClass, DebugKind, FailureType, ProfileStatus, RetentionClass, SourceService
from creative_workflow.worker.browser.flows.base import BrowserFlowError, FlowExecutionResult
from creative_workflow.worker.browser.flows.desktop_browser_flow import DesktopBrowserFlow

FREEPIK_GENERATOR_URL = "https://www.freepik.com/ai/image-generator"


class FreepikImageFlow(DesktopBrowserFlow):
    service = SourceService.FREEPIK
    flow_name = "freepik_generate_image_from_prompt"

    def run(self, job: JobForWorker, input_paths: dict[str, Path]) -> FlowExecutionResult:
        prompt = job.inputs.get("prompt", "")
        if not prompt:
            raise BrowserFlowError(FailureType.INVALID_JOB_PAYLOAD, "Freepik job requires prompt.")

        job_dir = self.assets.prepare_job_dir(job.job_id)
        download_dir = job_dir / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        steps: list[dict] = []

        steps.append({"step": "invoke_claude_browser"})
        raw_result = self._run_claude_browser_task(
            self._build_task(prompt, download_dir),
            timeout_s=min(job.timeout_s, 300),
            allowed_tools="Bash,Read",
        )
        steps.append({"step": "result_received"})

        downloaded = self._collect_downloads(download_dir, raw_result)
        if not downloaded:
            raise BrowserFlowError(
                FailureType.DOWNLOAD_FAILED,
                f"No image files found in {download_dir} after task. Claude result: {raw_result[:200]}",
            )
        steps.append({"step": "downloads_collected", "count": len(downloaded)})

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
            debug_asset_ids=[step_log_id],
            external_urls=[],
        )
        return FlowExecutionResult(
            flow_result=flow.model_dump(mode="json"),
            artifact_ids=generated_ids,
            debug_asset_ids=[step_log_id],
        )

    def _build_task(self, prompt: str, download_dir: Path) -> str:
        save_dir = str(download_dir).replace("\\", "/")
        return (
            f"Open this URL in Chrome: {FREEPIK_GENERATOR_URL}\n"
            "You will see Freepik's AI image generator. Do the following steps:\n"
            "1. Find the prompt input field and fill it with exactly this text "
            "(copy it verbatim, do not change it):\n"
            f"   {prompt}\n"
            "2. Click the Generate button and wait until the images fully appear "
            "(this usually takes 30–90 seconds — wait patiently).\n"
            "3. Download all generated images by clicking the Download button for each one.\n"
            f"4. Use Bash to move all newly downloaded image files (jpg, png, webp) "
            f"to this directory: {save_dir}\n"
            "   To find the downloaded files, check the Windows Downloads folder: "
            "run `ls \"$env:USERPROFILE/Downloads\" | sort -Property LastWriteTime -Descending | select -First 5` "
            "to see the newest files, then move image files from there.\n"
            "5. After moving, return a JSON object in exactly this format:\n"
            '   {"filenames": ["file1.jpg", "file2.png"]}\n'
            "   List only the filenames (not full paths) of the files you moved."
        )

    def _collect_downloads(self, download_dir: Path, result_text: str) -> list[Path]:
        try:
            data = json.loads(result_text)
            filenames = data.get("filenames", [])
            found = [download_dir / f for f in filenames if (download_dir / f).exists()]
            if found:
                return found
        except (json.JSONDecodeError, AttributeError):
            pass
        # Fallback: scan download_dir for any image files Claude may have placed there
        return [
            p for p in download_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif"}
        ]
