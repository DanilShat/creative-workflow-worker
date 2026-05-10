"""Tool: submit_aftereffects_render — kick off a headless AE render.

Runs aerender on the designer laptop, returns the output path when the
render finishes. Long-running tools are fine in MCP — Claude Desktop
shows a "tool is running…" indicator while we wait.

Asset overrides are out of scope for B3.0; designer-side AE project
conventions handle that. B3.1 adds ExtendScript-driven property
overrides.
"""

from __future__ import annotations

from pathlib import Path

from creative_workflow.worker.dcc.aftereffects_runner import (
    AERenderError,
    AERenderRequest,
    run_aerender,
)
from creative_workflow.worker.mcp.schemas import (
    SubmitAfterEffectsRenderInput,
    SubmitAfterEffectsRenderOutput,
)


async def submit_aftereffects_render(
    payload: SubmitAfterEffectsRenderInput,
) -> SubmitAfterEffectsRenderOutput:
    req = AERenderRequest(
        project_path=Path(payload.project_path),
        comp_name=payload.comp_name,
        output_path=Path(payload.output_path),
        output_module=payload.output_module,
    )

    try:
        result = await run_aerender(req)
    except AERenderError as exc:
        return SubmitAfterEffectsRenderOutput(
            project_path=payload.project_path,
            comp_name=payload.comp_name,
            output_path=payload.output_path,
            duration_s=0.0,
            error=str(exc),
        )

    return SubmitAfterEffectsRenderOutput(
        project_path=payload.project_path,
        comp_name=payload.comp_name,
        output_path=str(result.output_path),
        duration_s=round(result.duration_s, 2),
        note=f"Rendered {payload.comp_name} in {result.duration_s:.1f}s.",
    )
