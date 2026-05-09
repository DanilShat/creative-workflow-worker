# Creative Workflow Worker

Designer-laptop worker application for the creative workflow automation system.

This repo owns:

- worker registration, heartbeat, polling, job claiming and completion
- artifact upload/download through the operator API
- Playwright persistent browser profiles
- Gemini and Freepik browser flow code
- Photoshop/After Effects boundary skeletons for later live integrations

The operator backend/UI lives in a separate repo:

```text
https://github.com/DanilShat/creative-workflow-operator
```

## Quick Start

Clone this repo on the designer laptop:

```powershell
cd C:\
git clone https://github.com/DanilShat/creative-workflow-worker.git C:\creative-workflow-worker\app
cd C:\creative-workflow-worker\app
```

Install and check:

```powershell
python -m pip install -e ".[test]"
python -m playwright install chromium
Copy-Item .env.worker.example .env.worker
notepad .env.worker
python -m creative_workflow.worker.cli config check
python -m creative_workflow.worker.cli healthcheck
```

Or run the setup script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_designer_one_click.ps1
```

Run:

```powershell
python -m creative_workflow.worker.cli run
```

Update later:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\update_designer_from_git.ps1
```

## Runtime Notes

Real worker tokens, browser profiles, temporary files and cookies stay local and
must never be committed. Commit only `.env.worker.example`.
