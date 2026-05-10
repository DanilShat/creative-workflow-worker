"""Photoshop action library — single source of truth.

Both the chat-driven UXP panel (via the agent gateway) and the headless
batch path (worker daemon spawning Photoshop scripts for B1-style jobs)
build their actions from this module. The panel is a thin executor; the
business logic of "what is a valid crop, which UXP call expresses it,
what concrete bounds does '5% off the right' translate to" lives here.

Each public factory returns an :class:`ActionDescriptor` with concrete
params the panel can execute generically — no per-action JS branching
required beyond the small dispatcher.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


ActionType = Literal["crop", "export", "get_context", "noop"]
ActionStatus = Literal["ok", "validation_error"]
Side = Literal["left", "right", "top", "bottom"]
ImageFormat = Literal["png", "jpg", "webp"]


class DocumentContext(BaseModel):
    """Snapshot of the active Photoshop document the panel sent us."""

    document_name: str | None = None
    document_width: int | None = None
    document_height: int | None = None
    active_layer: str | None = None
    selection_bounds: list[int] | None = None


class CropParams(BaseModel):
    bounds: dict[str, int] = Field(
        ...,
        description="Concrete crop rectangle in pixels: {left, top, right, bottom}.",
    )
    new_width: int
    new_height: int

    @field_validator("bounds")
    @classmethod
    def _bounds_have_four_sides(cls, v: dict[str, int]) -> dict[str, int]:
        required = {"left", "top", "right", "bottom"}
        if set(v.keys()) != required:
            raise ValueError(f"bounds must have exactly {required}")
        if v["right"] <= v["left"] or v["bottom"] <= v["top"]:
            raise ValueError("bounds must form a positive rectangle")
        return v


class ExportParams(BaseModel):
    format: ImageFormat
    target_path: str
    quality: int = Field(90, ge=1, le=100)


class ActionDescriptor(BaseModel):
    """The envelope the gateway hands to the panel.

    Generic by construction so the panel's dispatcher stays small. The
    panel reads ``type`` to pick a UXP call, then passes ``params``
    through. The worker is responsible for putting *concrete* values in
    ``params`` (final pixel bounds, resolved file path, etc.) so the
    panel doesn't redo any arithmetic or path resolution.
    """

    type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    status: ActionStatus = "ok"
    error: str | None = None
    issued_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ---------- Factories ----------


def make_noop(explanation: str = "", echo: dict[str, Any] | None = None) -> ActionDescriptor:
    return ActionDescriptor(
        type="noop",
        params={"echo": echo or {}},
        explanation=explanation or "(noop)",
    )


def make_get_context(explanation: str = "snapshot of active document") -> ActionDescriptor:
    return ActionDescriptor(
        type="get_context",
        params={},
        explanation=explanation,
    )


def make_crop(
    *,
    side: Side,
    percent: float,
    context: DocumentContext,
) -> ActionDescriptor:
    """Compute concrete crop bounds for an N% trim from one side.

    Designer says "crop tighter on the right by 5%" → we resolve that
    against the current document size and produce {left, top, right,
    bottom} in pixels.
    """

    if context.document_width is None or context.document_height is None:
        return _validation_error(
            "crop",
            params={"side": side, "percent": percent},
            error="Need an active document to crop. Open the document in Photoshop and try again.",
        )

    if not (1 <= percent <= 50):
        return _validation_error(
            "crop",
            params={"side": side, "percent": percent},
            error="crop percent must be between 1 and 50.",
        )

    w = context.document_width
    h = context.document_height
    trim_x = round(w * percent / 100)
    trim_y = round(h * percent / 100)

    if side == "left":
        bounds = {"left": trim_x, "top": 0, "right": w, "bottom": h}
    elif side == "right":
        bounds = {"left": 0, "top": 0, "right": w - trim_x, "bottom": h}
    elif side == "top":
        bounds = {"left": 0, "top": trim_y, "right": w, "bottom": h}
    else:  # bottom
        bounds = {"left": 0, "top": 0, "right": w, "bottom": h - trim_y}

    crop_params = CropParams(
        bounds=bounds,
        new_width=bounds["right"] - bounds["left"],
        new_height=bounds["bottom"] - bounds["top"],
    )
    return ActionDescriptor(
        type="crop",
        params=crop_params.model_dump(),
        explanation=f"Cropping {percent:g}% off the {side} ({crop_params.new_width}×{crop_params.new_height}).",
    )


def make_export(
    *,
    format: ImageFormat,
    context: DocumentContext,
    target_path: str | None = None,
    quality: int = 90,
) -> ActionDescriptor:
    """Build a concrete export descriptor.

    If ``target_path`` is omitted we derive a sensible default in the
    designer's worker-temp directory using the active doc name and a
    short timestamp suffix.
    """

    if context.document_name is None:
        return _validation_error(
            "export",
            params={"format": format},
            error="Need an active document to export. Open the document in Photoshop and try again.",
        )

    if target_path is None:
        stem = PurePosixPath(context.document_name).stem or "untitled"
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        target_path = f"exports/{stem}-{ts}.{format}"

    export_params = ExportParams(format=format, target_path=target_path, quality=quality)
    return ActionDescriptor(
        type="export",
        params=export_params.model_dump(),
        explanation=f"Exporting as {format} → {target_path}.",
    )


# ---------- Internals ----------


def _validation_error(type_: ActionType, *, params: dict[str, Any], error: str) -> ActionDescriptor:
    return ActionDescriptor(
        type=type_,
        params=params,
        explanation=error,
        status="validation_error",
        error=error,
    )
