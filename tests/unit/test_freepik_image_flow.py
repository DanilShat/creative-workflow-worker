"""Tests for FreepikImageFlow fallback download collection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from creative_workflow.shared.contracts.workers import JobForWorker
from creative_workflow.shared.enums import FailureType, JobType
from creative_workflow.worker.browser.flows.base import BrowserFlowError
from creative_workflow.worker.browser.flows.freepik_image import (
    FreepikImageFlow,
    _collect_new_downloads,
    _snapshot_downloads,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(inputs: dict | None = None) -> JobForWorker:
    return JobForWorker(
        job_id="job_freepik_01",
        task_id="task_01",
        run_id="run_01",
        job_type=JobType.BROWSER_FLOW,
        required_capability="browser.freepik",
        action_name="freepik_generate_image_from_prompt",
        inputs=inputs or {"prompt": "A hero product image on white background."},
        input_assets=[],
        timeout_s=300,
        lease_ttl_s=60,
        lease_expires_at="2099-01-01T00:00:00Z",
        idempotency_key="idem_01",
    )


def _make_flow(tmp_path: Path) -> FreepikImageFlow:
    assets = MagicMock()
    assets.prepare_job_dir.return_value = tmp_path / "job_dir"
    (tmp_path / "job_dir" / "downloads").mkdir(parents=True, exist_ok=True)
    asset_counter = [0]

    def fake_upload(path, **_kw):
        asset_counter[0] += 1
        return f"asset_{asset_counter[0]:03d}"

    assets.upload_artifact.side_effect = fake_upload
    return FreepikImageFlow(profiles=MagicMock(), assets=assets)


# ---------------------------------------------------------------------------
# Happy path: Claude returns JSON and files are in download_dir
# ---------------------------------------------------------------------------

def test_claude_json_result_uploads_generated_assets(tmp_path: Path) -> None:
    flow = _make_flow(tmp_path)
    job = _make_job()
    download_dir = tmp_path / "job_dir" / "downloads"

    img = download_dir / "product_gen.png"
    img.write_bytes(b"\x89PNG")

    result_json = '{"filenames": ["product_gen.png"]}'

    with patch.object(flow, "_run_claude_browser_task", return_value=result_json):
        exec_result = flow.run(job, {})

    assert exec_result.artifact_ids, "expected at least one generated asset ID"
    assert len(exec_result.artifact_ids) == 1


# ---------------------------------------------------------------------------
# Fallback path: Claude raises non-auth BrowserFlowError, new file in Downloads
# ---------------------------------------------------------------------------

def test_fallback_collects_download_when_claude_hits_max_turns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    user_dl = tmp_path / "Downloads"
    user_dl.mkdir()
    new_img = user_dl / "magnific__shot_97683.png"
    new_img.write_bytes(b"\x89PNG")

    flow = _make_flow(tmp_path)
    job = _make_job()
    download_dir = tmp_path / "job_dir" / "downloads"

    error = BrowserFlowError(FailureType.SELECTOR_BROKEN, "error_max_turns reached")

    with patch.object(flow, "_run_claude_browser_task", side_effect=error):
        with patch(
            "creative_workflow.worker.browser.flows.freepik_image._snapshot_downloads",
            return_value=frozenset(),
        ):
            exec_result = flow.run(job, {})

    assert exec_result.artifact_ids, "expected generated asset from fallback scan"
    collected = list(download_dir.iterdir())
    assert any("magnific" in p.name for p in collected)


# ---------------------------------------------------------------------------
# Fallback path: no files anywhere -> DOWNLOAD_FAILED
# ---------------------------------------------------------------------------

def test_no_files_anywhere_raises_download_failed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "Downloads").mkdir()

    flow = _make_flow(tmp_path)
    job = _make_job()

    error = BrowserFlowError(FailureType.SELECTOR_BROKEN, "error_max_turns reached")

    with patch.object(flow, "_run_claude_browser_task", side_effect=error):
        with patch(
            "creative_workflow.worker.browser.flows.freepik_image._snapshot_downloads",
            return_value=frozenset(),
        ):
            with pytest.raises(BrowserFlowError) as exc_info:
                flow.run(job, {})

    assert exc_info.value.failure_type == FailureType.DOWNLOAD_FAILED


# ---------------------------------------------------------------------------
# Auth error is re-raised immediately without fallback scan
# ---------------------------------------------------------------------------

def test_needs_reauth_propagates_without_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "Downloads").mkdir()

    flow = _make_flow(tmp_path)
    job = _make_job()

    auth_error = BrowserFlowError(FailureType.NEEDS_REAUTH, "Claude CLI not logged in")

    with patch.object(flow, "_run_claude_browser_task", side_effect=auth_error):
        with pytest.raises(BrowserFlowError) as exc_info:
            flow.run(job, {})

    assert exc_info.value.failure_type == FailureType.NEEDS_REAUTH


# ---------------------------------------------------------------------------
# _collect_new_downloads module-level helper
# ---------------------------------------------------------------------------

def test_collect_new_downloads_moves_new_image_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    dl = tmp_path / "Downloads"
    dl.mkdir()

    old_img = dl / "old_image.png"
    old_img.write_bytes(b"\x89PNG")
    before = frozenset([old_img.name])

    new_img = dl / "new_gen.jpg"
    new_img.write_bytes(b"\xff\xd8\xff")

    dest = tmp_path / "dest"
    dest.mkdir()

    collected = _collect_new_downloads(before, dest)

    assert len(collected) == 1
    assert collected[0].name == "new_gen.jpg"
    assert (dest / "new_gen.jpg").exists()
    assert not new_img.exists()


def test_collect_new_downloads_ignores_non_image_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    dl = tmp_path / "Downloads"
    dl.mkdir()

    (dl / "report.pdf").write_bytes(b"%PDF")
    (dl / "gen.png").write_bytes(b"\x89PNG")

    dest = tmp_path / "dest"
    dest.mkdir()

    collected = _collect_new_downloads(frozenset(), dest)

    assert len(collected) == 1
    assert collected[0].name == "gen.png"
