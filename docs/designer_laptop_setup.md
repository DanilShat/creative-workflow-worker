# Designer Laptop Setup

Clone this repo on the designer laptop:

## Setup

```powershell
cd C:\
git clone https://github.com/DanilShat/creative-workflow-worker.git C:\creative-workflow-worker\app
cd C:\creative-workflow-worker\app
powershell -ExecutionPolicy Bypass -File .\scripts\setup_designer_one_click.ps1
```

The setup script installs Python dependencies, installs Playwright Chromium,
checks `.env.worker`, checks server reachability, then opens Gemini and Freepik
profile setup.

## Manual login

When the browser opens:

1. Log in to Gemini.
2. Return to PowerShell and press Enter.
3. Log in to Freepik.
4. Return to PowerShell and press Enter.

The worker uses persistent profiles stored under `PLAYWRIGHT_PROFILE_ROOT`.
Do not use your normal browser profile for automation.

If Google OAuth rejects the Freepik login as an unsafe browser, install Google
Chrome on the designer laptop and add this line to `.env.worker`:

```powershell
PLAYWRIGHT_BROWSER_CHANNEL=chrome
```

Then rerun `python -m creative_workflow.worker.cli profile setup freepik`.
This keeps the automation profile separate while using the system Chrome
browser engine.

If the account is already authenticated in the normal Chrome profile and cannot
approve another device, do not keep trying to clone cookies as part of Gate A.
That path is fragile and has been moved to V2 as Claude Desktop / desktop UI
automation over the already trusted browser session.

The old profile clone script is kept only as an experimental diagnostic:

```powershell
cd C:\creative-workflow-worker\app
powershell -ExecutionPolicy Bypass -File .\scripts\clone_chrome_profile_for_worker.ps1 -ProfileDirectory Default
```

Clean experimental copied profiles with:

```powershell
cd C:\creative-workflow-worker\app
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_designer_experimental_profiles.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\cleanup_designer_experimental_profiles.ps1 -Apply
```

The cleanup script deletes only worker-owned copies under
`C:\creative-workflow-worker` unless the optional Playwright cache switch is
explicitly provided. It does not touch the real Chrome profile in AppData.

## Run worker

```powershell
python -m creative_workflow.worker.cli run
```

Keep this terminal open while the operator runs Gate A.

## Photoshop and After Effects

No Photoshop or After Effects process is required for Gate A. If a DCC job is
accidentally issued, the worker should report the explicit unavailable failure
instead of attempting arbitrary host-app code.
