"""Action registry — turn an LLM envelope into a concrete ActionDescriptor."""

from __future__ import annotations

from typing import Any

from creative_workflow.worker.agent_gateway.llm.envelope import LLMEnvelope
from creative_workflow.worker.agent_gateway.schemas import DocumentContext as ChatDocumentContext
from creative_workflow.worker.dcc.photoshop_actions import (
    ActionDescriptor,
    DocumentContext,
    make_crop,
    make_export,
    make_get_context,
    make_noop,
)


_ALLOWED = {"crop", "export", "get_context", "noop"}


class UnknownAction(ValueError):
    """The LLM emitted an action_type not on the allowlist."""


def _to_action_context(ctx: ChatDocumentContext | None) -> DocumentContext:
    if ctx is None:
        return DocumentContext()
    return DocumentContext.model_validate(ctx.model_dump())


def materialize(
    envelope: LLMEnvelope,
    chat_context: ChatDocumentContext | None,
) -> ActionDescriptor:
    """Translate a validated LLM envelope into a concrete action.

    Raises :class:`UnknownAction` for off-allowlist action_types so the
    router can return a designer-friendly rejection. Returns an
    :class:`ActionDescriptor` with status='validation_error' for
    parameter-level problems (out of range, missing required field, no
    active document, etc.).
    """

    action_type = envelope.action_type
    params: dict[str, Any] = envelope.params or {}
    explanation = envelope.explanation or ""
    doc_ctx = _to_action_context(chat_context)

    if action_type is None or action_type == "noop":
        return make_noop(explanation=explanation, echo=params)

    if action_type not in _ALLOWED:
        raise UnknownAction(
            f"Action '{action_type}' is not allowed. "
            f"Allowed: {sorted(_ALLOWED)}."
        )

    if action_type == "get_context":
        return make_get_context(explanation=explanation or "snapshot of active document")

    if action_type == "crop":
        side = params.get("side")
        percent = params.get("percent")
        if side not in {"left", "right", "top", "bottom"} or not isinstance(percent, (int, float)):
            return ActionDescriptor(
                type="crop",
                params=params,
                explanation="crop needs a valid side and percent.",
                status="validation_error",
                error="crop needs side ∈ {left,right,top,bottom} and a numeric percent.",
            )
        return make_crop(side=side, percent=float(percent), context=doc_ctx)

    if action_type == "export":
        fmt = params.get("format")
        if fmt not in {"png", "jpg", "webp"}:
            return ActionDescriptor(
                type="export",
                params=params,
                explanation="export needs a format ∈ {png,jpg,webp}.",
                status="validation_error",
                error="export.format must be png, jpg, or webp.",
            )
        return make_export(
            format=fmt,
            context=doc_ctx,
            target_path=params.get("target_path"),
            quality=int(params.get("quality", 90)),
        )

    # Defensive — _ALLOWED already gated this.
    raise UnknownAction(f"Unhandled action_type '{action_type}'.")
