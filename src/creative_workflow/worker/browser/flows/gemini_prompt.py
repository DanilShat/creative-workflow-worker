"""Live Gemini browser flow for building a Freepik generation prompt."""

from pathlib import Path
import re
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from creative_workflow.shared.contracts.jobs import BrowserFlowResult, GeminiPromptOutput
from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import AssetClass, DebugKind, FailureType, ProfileStatus, RetentionClass, SourceService
from creative_workflow.worker.browser.flows.base import BaseBrowserFlow, BrowserFlowError, FlowExecutionResult
from creative_workflow.worker.browser.launch import persistent_context_options
from creative_workflow.worker.browser.profiles import SERVICE_URLS

PHOTO_GEM_URL = "https://gemini.google.com/gem/5f69a5afc4b5"
VIDEO_GEM_URL = "https://gemini.google.com/gem/21d5be0eae0a"


class GeminiPromptFlow(BaseBrowserFlow):
    service = SourceService.GEMINI
    flow_name = "gemini_build_prompt_from_brief_and_refs"

    def run(self, job: JobForWorker, input_paths: dict[str, Path]) -> FlowExecutionResult:
        job_dir = self.assets.prepare_job_dir(job.job_id)
        steps: list[dict] = []
        raw_text_path = job_dir / "debug" / "gemini_response.txt"
        screenshot_path = job_dir / "debug" / "gemini_final.png"
        try:
            with sync_playwright() as pw:
                print(f"[gemini] launching browser profile {self.profiles.profile_dir('gemini')}", flush=True)
                context = pw.chromium.launch_persistent_context(
                    **persistent_context_options(self.profiles.profile_dir("gemini")),
                )
                page = context.new_page()
                steps.append({"step": "open_service"})
                gemini_url = self._gemini_url(job)
                print(f"[gemini] opening {gemini_url}", flush=True)
                page.goto(gemini_url, wait_until="domcontentloaded", timeout=60000)
                status = self.profiles.validate_open_page("gemini", page)
                print(f"[gemini] profile status {status.value}", flush=True)
                self.profiles.save_status("gemini", status)
                if status != ProfileStatus.AUTHENTICATED:
                    raise BrowserFlowError(FailureType.NEEDS_REAUTH, f"Gemini profile status is {status.value}.")

                prompt = self._build_gemini_instruction(job)
                steps.append({"step": "fill_prompt"})
                print("[gemini] waiting for composer", flush=True)
                composer = self._open_composer(page)
                print("[gemini] filling prompt", flush=True)
                composer.fill(prompt)
                steps.append({"step": "submit"})
                print("[gemini] submitting prompt", flush=True)
                page.keyboard.press("Control+Enter")
                try:
                    page.get_by_role("button", name=re.compile("send|submit", re.I)).click(timeout=5000)
                except PlaywrightTimeoutError:
                    page.keyboard.press("Enter")

                steps.append({"step": "wait_for_result"})
                print("[gemini] waiting for response text", flush=True)
                body_text = self._wait_for_response_text(page, timeout_s=min(job.timeout_s, 180))
                raw_text_path.parent.mkdir(parents=True, exist_ok=True)
                raw_text_path.write_text(body_text, encoding="utf-8")
                page.screenshot(path=str(screenshot_path), full_page=True)
                context.close()
        except BrowserFlowError:
            raise
        except PlaywrightTimeoutError as exc:
            raise BrowserFlowError(FailureType.NETWORK_TEMPORARY, f"Gemini flow timed out: {exc}") from exc
        except Exception as exc:
            raise BrowserFlowError(FailureType.SELECTOR_BROKEN, f"Gemini flow failed: {exc}") from exc

        prompt_text = self._extract_prompt_text(raw_text_path.read_text(encoding="utf-8"))
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
        screenshot_id = self.assets.upload_artifact(
            screenshot_path,
            task_id=job.task_id,
            run_id=job.run_id,
            job_id=job.job_id,
            asset_class=AssetClass.DEBUG,
            retention_class=RetentionClass.DEBUG_TTL_7D,
            source_service=SourceService.GEMINI,
            content_type="image/png",
            debug_kind=DebugKind.SCREENSHOT,
        )
        step_log_id = self._upload_step_log(self._write_step_log(job_dir, steps), job)
        structured = GeminiPromptOutput(
            prompt_text=prompt_text,
            negative_prompt=None,
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
            debug_asset_ids=[raw_asset_id, screenshot_id, step_log_id],
            external_urls=[],
        )
        return FlowExecutionResult(flow_result=flow.model_dump(mode="json"), debug_asset_ids=[raw_asset_id, screenshot_id, step_log_id])

    def _build_gemini_instruction(self, job: JobForWorker) -> str:
        refs = ", ".join(job.inputs.get("reference_asset_ids", []))
        return (
            "You are preparing a prompt for Freepik AI image generation. "
            "Return only the final prompt text, no markdown. "
            f"Brief: {job.inputs.get('brief_text', '')}\n"
            f"Operator note: {job.inputs.get('operator_note') or ''}\n"
            f"Reference asset ids available to the workflow: {refs}\n"
            "The prompt should be specific, visual, production-ready, and suitable for a static product hero image."
        )

    def _extract_prompt_text(self, body_text: str) -> str:
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        useful = [line for line in lines if len(line) > 80 and "freepik" not in line.lower()]
        if useful:
            return useful[-1][:4000]
        if lines:
            return lines[-1][:4000]
        raise BrowserFlowError(FailureType.SELECTOR_BROKEN, "Gemini response text could not be extracted.")

    def _open_composer(self, page):
        composer = page.locator("textarea, [contenteditable='true']").first
        try:
            composer.wait_for(timeout=10000)
            return composer
        except PlaywrightTimeoutError:
            pass

        for label in ["Start chat", "Chat", "Use Gem", "New chat", "Try it"]:
            try:
                page.get_by_role("button", name=re.compile(label, re.I)).click(timeout=5000)
                composer.wait_for(timeout=15000)
                return composer
            except PlaywrightTimeoutError:
                continue

        try:
            page.locator("a, button").filter(has_text=re.compile("start|chat|use", re.I)).first.click(timeout=5000)
            composer.wait_for(timeout=15000)
            return composer
        except PlaywrightTimeoutError as exc:
            raise BrowserFlowError(FailureType.SELECTOR_BROKEN, "Gemini composer did not appear on the Gem page.") from exc

    def _wait_for_response_text(self, page, timeout_s: int) -> str:
        deadline = time.monotonic() + timeout_s
        last_text = ""
        while time.monotonic() < deadline:
            body_text = page.locator("body").inner_text(timeout=10000)
            last_text = body_text
            if self._extract_candidate_prompt(body_text):
                return body_text
            page.wait_for_timeout(3000)
        debug_tail = last_text[-1000:] if last_text else "(empty page text)"
        raise BrowserFlowError(FailureType.NETWORK_TEMPORARY, f"Gemini response did not stabilize. Last page text: {debug_tail}")

    def _gemini_url(self, job: JobForWorker) -> str:
        configured = job.inputs.get("gemini_url")
        if configured:
            return configured
        output_type = str(job.inputs.get("requested_output_type") or "").lower()
        if "video" in output_type:
            return VIDEO_GEM_URL
        return PHOTO_GEM_URL or SERVICE_URLS["gemini"]

    def _extract_candidate_prompt(self, body_text: str) -> str | None:
        lines = [line.strip() for line in body_text.splitlines() if line.strip()]
        useful = [line for line in lines if len(line) > 80 and "freepik" not in line.lower()]
        return useful[-1] if useful else None
