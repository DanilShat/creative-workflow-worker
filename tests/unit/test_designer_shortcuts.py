from pathlib import Path


def test_designer_shortcut_script_creates_single_launcher_for_existing_start_script() -> None:
    scripts = Path("scripts")
    shortcut_script = (scripts / "create_designer_shortcuts.ps1").read_text(encoding="utf-8")

    assert (scripts / "start_designer_app.ps1").exists()
    assert "Creative Workflow Worker.cmd" in shortcut_script
    assert "Creative Workflow.cmd" in shortcut_script
    assert "start_designer_app.ps1" in shortcut_script
    assert "CreateShortcut" not in shortcut_script
