"""Pre-built designer workflows as MCP Prompts.

Claude Desktop surfaces these as slash-menu items so the chat feels like a
creative tool with verbs ('Brief to variants', 'PSD handoff', 'Reels
render') rather than a blank text box.

Each prompt returns a templated user message that the designer can then
edit. The model sees it as if the designer typed it themselves, so tool
calls fire naturally afterwards.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base


def register_prompts(mcp: FastMCP) -> None:
    @mcp.prompt(
        name="brief-to-variants",
        description="Turn a written brief into a set of generated variants and review them.",
    )
    def brief_to_variants(
        title: str = "",
        brief: str = "",
        count: str = "8",
        existing_task_id: str = "",
    ) -> list[base.Message]:
        if existing_task_id:
            opener = (
                f"Use `submit_browser_job` with existing_task_id=`{existing_task_id}`, "
                f"variant_count={count}, and the brief below to fan out variants on a task "
                f"I've already set up in the operator UI."
            )
        else:
            opener = (
                f"Use `submit_browser_job` with title=`{title or '<short title>'}`, "
                f"variant_count={count}, and the brief below to start a new task."
            )

        body = (
            f"{opener}\n\n"
            f"Brief:\n\n"
            f"> {brief or '<paste the brief here>'}\n\n"
            f"After it returns:\n"
            f"1. Tell me how many jobs were queued.\n"
            f"2. Wait briefly, then call `list_artifacts(task_id, limit=20)` "
            f"and show me the results inline.\n"
            f"3. When I pick a winner, call `request_review` with the run_id "
            f"and my selection."
        )
        return [base.UserMessage(body)]

    @mcp.prompt(
        name="psd-handoff",
        description="Prepare selected artifacts for Photoshop handoff through the local panel.",
    )
    def psd_handoff(task_id: str, asset_ids: str = "") -> list[base.Message]:
        body = (
            f"I want to hand off the selected artifacts from task `{task_id}` "
            f"into our Photoshop comp.\n\n"
            f"Selected assets: {asset_ids or '<comma-separated asset_ids>'}\n\n"
            f"Use `list_artifacts` to confirm the selection, then prepare "
            f"the exact mapping each asset should use in the Photoshop panel. "
            f"The local Photoshop UXP panel handles allowlisted edit/export "
            f"actions through the agent gateway."
        )
        return [base.UserMessage(body)]

    @mcp.prompt(
        name="reels-render",
        description="Render a named After Effects comp through local aerender.",
    )
    def reels_render(
        task_id: str,
        project_path: str = "",
        comp_name: str = "Main_9x16",
        output_path: str = "",
        output_module: str = "Lossless",
    ) -> list[base.Message]:
        body = (
            f"I want to render an After Effects output for task `{task_id}`.\n\n"
            f"First use `get_context` and `list_artifacts` to confirm the "
            f"source assets are ready. Then call `submit_aftereffects_render` "
            f"with:\n\n"
            f"- project_path: `{project_path or '<absolute path to .aep>'}`\n"
            f"- comp_name: `{comp_name}`\n"
            f"- output_path: `{output_path or '<absolute output file path>'}`\n"
            f"- output_module: `{output_module}`\n\n"
            f"If the tool reports that `aerender.exe` is missing, explain "
            f"that the designer must install After Effects or set "
            f"`AERENDER_EXE` in `.env.worker`."
        )
        return [base.UserMessage(body)]
