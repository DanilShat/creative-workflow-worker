"""Common envelope returned by every LLM client."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Complexity = Literal["mechanical", "creative"]


class LLMEnvelope(BaseModel):
    """Output envelope from Ollama or Claude.

    The local model emits this directly via JSON-mode. Claude is asked
    to emit the same shape so the router treats both uniformly.
    """

    action_type: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    needs_claude: bool = False
    complexity: Complexity = "mechanical"
    explanation: str = ""
