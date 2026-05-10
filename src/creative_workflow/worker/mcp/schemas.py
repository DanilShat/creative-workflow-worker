"""Pydantic schemas for MCP tool inputs and outputs.

Every tool exchanged with Claude Desktop has a typed contract here so
the operator boundary stays narrow and auditable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ArtifactSummary(BaseModel):
    asset_id: str
    task_id: str
    asset_class: str
    content_type: str
    filename: str
    size_bytes: int
    download_url: str


class JobSummary(BaseModel):
    job_id: str
    task_id: str
    job_type: str
    action_name: str
    status: Literal["pending", "in_progress", "succeeded", "failed", "cancelled"]
    started_at: datetime | None = None
    finished_at: datetime | None = None


class GetContextInput(BaseModel):
    task_id: str = Field(..., description="The task to fetch context for.")


class GetContextOutput(BaseModel):
    task_id: str
    title: str | None = None
    brief: str | None = None
    jobs: list[JobSummary]
    artifact_count: int


class ListArtifactsInput(BaseModel):
    task_id: str = Field(..., description="Task whose artifacts to list.")
    asset_class: str | None = Field(
        None,
        description="Optional filter — e.g. 'generated', 'reference', 'final'.",
    )
    inline_images: bool = Field(
        True,
        description=(
            "When true, image artifacts are returned as inline image content "
            "blocks so Claude Desktop can render thumbnails in the chat."
        ),
    )
    limit: int = Field(20, ge=1, le=100)


class ListArtifactsOutput(BaseModel):
    task_id: str
    artifacts: list[ArtifactSummary]


class RequestReviewInput(BaseModel):
    task_id: str
    run_id: str
    decision: Literal["approved", "rejected"]
    selected_asset_id: str | None = None
    reason: str | None = Field(
        None,
        description="Short note from the designer explaining the decision.",
    )


class RequestReviewOutput(BaseModel):
    task_id: str
    run_id: str
    decision: str
    submitted_at: datetime


class SubmitBrowserJobInput(BaseModel):
    title: str = Field(..., description="Short label for the task ('Spring drop hero').")
    brief: str = Field(..., description="The natural-language brief.")
    variant_count: int = Field(8, ge=1, le=20)
    existing_task_id: str | None = Field(
        None,
        description=(
            "If set, fan out variants on this task instead of creating a new "
            "one. Useful when the designer already attached references via "
            "the operator UI."
        ),
    )
    requested_output_type: str = Field("static_image")


class SubmitBrowserJobOutput(BaseModel):
    task_id: str
    run_id: str
    job_ids: list[str]
    workflow_state: str
    variant_count: int
    note: str | None = None


class SubmitAfterEffectsRenderInput(BaseModel):
    project_path: str = Field(..., description="Absolute path to the .aep project on the designer laptop.")
    comp_name: str = Field(..., description="Name of the comp inside the project to render.")
    output_path: str = Field(..., description="Absolute path for the rendered output file.")
    output_module: str = Field(
        "Lossless",
        description=(
            "After Effects output module template. Use the name of a "
            "template you've saved in AE — defaults to the built-in "
            "'Lossless' template (writes MOV)."
        ),
    )


class SubmitAfterEffectsRenderOutput(BaseModel):
    project_path: str
    comp_name: str
    output_path: str
    duration_s: float
    note: str | None = None
    error: str | None = None
