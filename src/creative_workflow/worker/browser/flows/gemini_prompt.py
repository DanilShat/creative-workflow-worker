"""Gemini browser flow powered by Claude Code CLI desktop-browser mode."""

from pathlib import Path

from creative_workflow.shared.contracts.jobs import BrowserFlowResult, GeminiPromptOutput
from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import AssetClass, DebugKind, ProfileStatus, RetentionClass, SourceService
from creative_workflow.worker.browser.flows.base import FlowExecutionResult
from creative_workflow.worker.browser.flows.desktop_browser_flow import DesktopBrowserFlow

PHOTO_GEM_URL = "https://gemini.google.com/gem/5f69a5afc4b5"
VIDEO_GEM_URL = "https://gemini.google.com/gem/21d5be0eae0a"


class GeminiPromptFlow(DesktopBrowserFlow):
    service = SourceService.GEMINI
    flow_name = "gemini_build_prompt_from_brief_and_refs"

    def run(self, job: JobForWorker, input_paths: dict[str, Path]) -> FlowExecutionResult:
        job_dir = self.assets.prepare_job_dir(job.job_id)
        steps: list[dict] = []
        raw_text_path = job_dir / "debug" / "gemini_response.txt"

        steps.append({"step": "invoke_claude_browser"})
        gemini_url = self._gemini_url(job)
        result_text = self._run_claude_browser_task(
            self._build_task(job, gemini_url),
            timeout_s=min(job.timeout_s, 240),
        )
        steps.append({"step": "result_received", "length": len(result_text)})

        raw_text_path.parent.mkdir(parents=True, exist_ok=True)
        raw_text_path.write_text(result_text, encoding="utf-8")

        raw_asset_id = self.assets.upload_artifact(
            raw_text_path,
            task_id=job.task_id,
            run_id=job.run_id,
            job_id=job.job_id,
            asset_class=AssetClass.DEBUG,
            retention_class=RetentionClass.DEBUG_TTL_7D,
            source_service=SourceService.GEMINI,
            content_type="text/plain",
            debug_kind=DebugKind.RAW_TEXT,
        )
        step_log_id = self._upload_step_log(self._write_step_log(job_dir, steps), job)
        structured = GeminiPromptOutput(
            prompt_text=result_text[:4000],
            prompt_language="en",
            extracted_from_response=True,
            raw_response_asset_id=raw_asset_id,
        )
        flow = BrowserFlowResult(
            service=SourceService.GEMINI,
            flow_name=self.flow_name,
            profile_status=ProfileStatus.AUTHENTICATED,
            structured_output=structured.model_dump(),
            artifact_ids=[],
            debug_asset_ids=[raw_asset_id, step_log_id],
            external_urls=[],
        )
        return FlowExecutionResult(
            flow_result=flow.model_dump(mode="json"),
            debug_asset_ids=[raw_asset_id, step_log_id],
        )

    def _build_task(self, job: JobForWorker, gemini_url: str) -> str:
        brief = job.inputs.get("brief_text", "")
        note = job.inputs.get("operator_note") or ""
        refs = ", ".join(job.inputs.get("reference_asset_ids", []))
        instruction = (
            "You are preparing a prompt for Freepik AI image generation. "
            "Return only the final prompt text, no markdown. "
            f"Brief: {brief}\n"
            f"Operator note: {note}\n"
            f"Reference asset ids: {refs}\n"
            "The prompt should be specific, visual, production-ready, "
            "and suitable for a static product hero image."
        )
        return (
            f"Open this URL in Chrome: {gemini_url}\n"
            "You will see a Gemini Gem interface with a chat composer.\n"
            "Fill the composer with exactly this instruction (do not modify it):\n"
            "---\n"
            f"{instruction}\n"
            "---\n"
            "Submit the message and wait for Gemini to fully respond.\n"
            "Once the response is complete, return ONLY the generated prompt text "
            "from Gemini's response. Do not include your own explanation or the "
            "original instruction — just the prompt text Gemini wrote."
        )

    def _gemini_url(self, job: JobForWorker) -> str:
        configured = job.inputs.get("gemini_url")
        if configured:
            return configured
        if "video" in str(job.inputs.get("requested_output_type") or "").lower():
            return VIDEO_GEM_URL
        return PHOTO_GEM_URL
