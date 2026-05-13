"""Base class for Claude Code CLI desktop-browser flows.

Replaces Playwright isolated profiles. Claude operates the designer's
already-authenticated daily Chrome session via --chrome, so Google OAuth
and provider trust checks run against a browser the provider already knows.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from creative_workflow.shared.enums import FailureType
from creative_workflow.worker.assets.manager import WorkerAssetManager
from creative_workflow.worker.browser.flows.base import BaseBrowserFlow, BrowserFlowError
from creative_workflow.worker.browser.profiles import ProfileManager


class DesktopBrowserFlow(BaseBrowserFlow):
    """Browser flow that drives Chrome via `claude --chrome -p`."""

    def __init__(self, profiles: ProfileManager, assets: WorkerAssetManager) -> None:
        super().__init__(profiles, assets)

    def _claude_exe(self) -> str:
        return os.getenv("CLAUDE_CLI_EXECUTABLE", "claude")

    def _run_claude_browser_task(
        self,
        task: str,
        timeout_s: int,
        allowed_tools: str = "Read",
    ) -> str:
        """Invoke `claude --chrome -p` with task. Returns the result text string."""
        cmd = [
            self._claude_exe(),
            "--chrome",
            "-p",
            "--model", "claude-haiku-4-5-20251001",
            "--output-format", "json",
            "--permission-mode", "bypassPermissions",
            "--allowedTools", allowed_tools,
            "--max-turns", "25",
            task,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
        except FileNotFoundError as exc:
            raise BrowserFlowError(
                FailureType.DEPENDENCY_UNAVAILABLE,
                f"Claude Code CLI not found on PATH (CLAUDE_CLI_EXECUTABLE={self._claude_exe()}): {exc}",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise BrowserFlowError(
                FailureType.NETWORK_TEMPORARY,
                f"Claude browser task timed out after {timeout_s}s.",
            ) from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            if any(k in stderr.lower() for k in ("not logged", "log in", "login", "authenticate")):
                raise BrowserFlowError(
                    FailureType.NEEDS_REAUTH,
                    f"Claude CLI not logged in: {stderr[:400]}",
                )
            raise BrowserFlowError(
                FailureType.SELECTOR_BROKEN,
                f"Claude browser task exited {proc.returncode}: {stderr[:400]}",
            )

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise BrowserFlowError(
                FailureType.SELECTOR_BROKEN,
                f"Claude CLI produced non-JSON output: {proc.stdout[:300]}",
            ) from exc

        result = str(payload.get("result") or "").strip()
        if not result:
            raise BrowserFlowError(
                FailureType.SELECTOR_BROKEN,
                f"Claude returned empty result. Payload: {str(payload)[:300]}",
            )
        return result
