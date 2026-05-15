"""Freepik image generation flow powered by Claude Code CLI desktop-browser mode."""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
import shutil

from creative_workflow.shared.contracts.jobs import BrowserFlowResult, FreepikGenerationOutput
from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import AssetClass, DebugKind, FailureType, ProfileStatus, RetentionClass, SourceService
from creative_workflow.worker.browser.flows.base import BrowserFlowError, FlowExecutionResult
from creative_workflow.worker.browser.flows.desktop_browser_flow import DesktopBrowserFlow

FREEPIK_GENERATOR_URL = "https://www.freepik.com/ai/image-generator"
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# Auth / dependency errors must not be swallowed by the fallback scan
_HARD_FAILURE_TYPES = {FailureType.NEEDS_REAUTH, FailureType.DEPENDENCY_UNAVAILABLE}


def _user_downloads_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", Path.home())) / "Downloads"


def _snapshot_downloads() -> frozenset[str]:
    d = _user_downloads_dir()
    if not d.is_dir():
        return frozenset()
    return frozenset(p.name for p in d.iterdir() if p.is_file())


def _collect_new_downloads(before: frozenset[str], dest: Path) -> list[Path]:
    """Move image files from user Downloads that were not in *before* into *dest*."""
    d = _user_downloads_dir()
    if not d.is_dir():
        return []
    collected: list[Path] = []
    for p in sorted(d.iterdir()):
        if not p.is_file() or p.suffix.lower() not in _IMAGE_EXTENSIONS:
            continue
        if p.name in before:
            continue
        dest_path = dest / p.name
        try:
            shutil.move(str(p), str(dest_path))
        except OSError:
            continue
        collected.append(dest_path)
    return collected


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

        downloads_before = _snapshot_downloads()
        steps.append({"step": "snapshot_downloads", "count": len(downloads_before)})

        steps.append({"step": "invoke_claude_browser"})
        raw_result = ""
        claude_error: str | None = None
        try:
            raw_result = self._run_claude_browser_task(
                self._build_task(prompt, download_dir, job.inputs),
                timeout_s=min(job.timeout_s, 300),
                allowed_tools="Bash,Read",
            )
            steps.append({"step": "result_received"})
        except BrowserFlowError as exc:
            if exc.failure_type in _HARD_FAILURE_TYPES:
                raise
            claude_error = f"{exc.failure_type.value}: {exc.message}"
            raw_result = claude_error
            steps.append({"step": "claude_error", "error": claude_error[:200]})

        # Always upload the raw Claude result for debugging
        debug_text_path = job_dir / "debug" / "freepik_claude_result.txt"
        debug_text_path.parent.mkdir(parents=True, exist_ok=True)
        debug_text_path.write_text(raw_result, encoding="utf-8")
        debug_asset_id = self.assets.upload_artifact(
            debug_text_path,
            task_id=job.task_id,
            run_id=job.run_id,
            job_id=job.job_id,
            asset_class=AssetClass.DEBUG,
            retention_class=RetentionClass.DEBUG_TTL_7D,
            source_service=SourceService.FREEPIK,
            content_type="text/plain",
            debug_kind=DebugKind.RAW_TEXT,
        )

        downloaded = self._collect_downloads(download_dir, raw_result)
        if not downloaded:
            steps.append({"step": "fallback_download_scan"})
            downloaded = _collect_new_downloads(downloads_before, download_dir)
            if downloaded:
                steps.append({"step": "fallback_collected", "count": len(downloaded)})

        if not downloaded:
            raise BrowserFlowError(
                FailureType.DOWNLOAD_FAILED,
                f"No image files found in {download_dir} or Downloads after task. Claude result: {raw_result[:200]}",
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
            debug_asset_ids=[debug_asset_id, step_log_id],
            external_urls=[],
        )
        return FlowExecutionResult(
            flow_result=flow.model_dump(mode="json"),
            artifact_ids=generated_ids,
            debug_asset_ids=[debug_asset_id, step_log_id],
        )

    def _build_task(self, prompt: str, download_dir: Path, inputs: dict) -> str:
        save_dir = str(download_dir)
        aspect = (inputs.get("settings") or {}).get("aspect_ratio", "4:5")
        source_note = ""
        if inputs.get("source_asset_id"):
            source_note = (
                "\nThis prompt is based on a specific product packshot image. "
                "Do not use it as a mood reference — it is the product anchor.\n"
            )
        return (
            f"Open this URL in Chrome: {FREEPIK_GENERATOR_URL}\n"
            "You will see Freepik's AI image generator. Do the following steps:\n"
            f"1. If there is an aspect ratio or canvas size control, set it to {aspect}.\n"
            f"{source_note}"
            "2. Find the prompt input field and fill it with exactly this text "
            "(copy it verbatim, do not change it):\n"
            f"   {prompt}\n"
            "3. Click the Generate button and wait until the images fully appear "
            "(this usually takes 30-90 seconds - wait patiently).\n"
            "4. Download all generated images by clicking the Download button for each one.\n"
            f"5. Use PowerShell to move all newly downloaded image files (jpg, png, webp) "
            f"to this directory: {save_dir}\n"
            "   To find the downloaded files, run this PowerShell command:\n"
            "   Get-ChildItem \"$env:USERPROFILE\\Downloads\" | "
            "Sort-Object LastWriteTime -Descending | "
            "Select-Object -First 10 | Format-List Name, LastWriteTime\n"
            "   Then move each image file:\n"
            f"   Move-Item \"$env:USERPROFILE\\Downloads\\<filename>\" -Destination \"{save_dir}\"\n"
            "6. After moving, return a JSON object in exactly this format:\n"
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
        return [
            p for p in download_dir.iterdir()
            if p.is_file() and p.suffix.lower() in _IMAGE_EXTENSIONS
        ]
