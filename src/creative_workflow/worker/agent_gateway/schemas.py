"""Request and response schemas for the agent gateway."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from creative_workflow.worker.dcc.photoshop_actions import ActionDescriptor


RoutedTo = Literal["ollama", "claude", "rejected"]


class DocumentContext(BaseModel):
    document_name: str | None = None
    document_width: int | None = None
    document_height: int | None = None
    active_layer: str | None = None
    selection_bounds: list[int] | None = Field(
        None,
        description="[left, top, right, bottom] when there is an active selection.",
    )


class ChatRequest(BaseModel):
    message: str = Field(..., description="The designer's message.")
    context: DocumentContext | None = None


class ChatResponse(BaseModel):
    kind: Literal["message", "action"]
    text: str | None = None
    action: ActionDescriptor | None = None
    routed_to: RoutedTo = "rejected"
