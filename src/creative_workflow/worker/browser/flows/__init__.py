"""Allowlisted browser flow registry."""

from creative_workflow.worker.browser.flows.freepik_image import FreepikImageFlow
from creative_workflow.worker.browser.flows.gemini_prompt import GeminiPromptFlow

FLOW_CLASSES = {
    "gemini_build_prompt_from_brief_and_refs": GeminiPromptFlow,
    "freepik_generate_image_from_prompt": FreepikImageFlow,
}

