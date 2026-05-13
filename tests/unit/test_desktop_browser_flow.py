from __future__ import annotations

import subprocess

from creative_workflow.worker.browser.flows.desktop_browser_flow import DesktopBrowserFlow


def test_claude_browser_command_reads_subscription_login(monkeypatch) -> None:
    """Browser mode must not use --bare because it disables OAuth/keychain auth."""

    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **_kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(cmd, 0, '{"result":"READY"}', "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = DesktopBrowserFlow(profiles=None, assets=None)._run_claude_browser_task(  # type: ignore[arg-type]
        "Return READY.",
        timeout_s=5,
    )

    assert result == "READY"
    assert "--chrome" in captured["cmd"]
    assert "--bare" not in captured["cmd"]
