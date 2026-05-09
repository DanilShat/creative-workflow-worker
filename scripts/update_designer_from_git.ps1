param(
    [string]$AppRoot = "C:\creative-workflow-worker\app",
    [string]$Branch = "main",
    [switch]$SkipInstall,
    [switch]$SkipPlaywrightInstall
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path (Join-Path $AppRoot ".git"))) {
    throw "No git checkout found at $AppRoot. Run scripts\switch_designer_to_git.ps1 first."
}

Set-Location $AppRoot

Write-Host "Updating designer worker from git..." -ForegroundColor Cyan
git fetch origin $Branch
git checkout $Branch
git pull --ff-only origin $Branch

if (-not (Test-Path ".env.worker")) {
    Copy-Item ".env.worker.example" ".env.worker"
    Write-Host "Created .env.worker from example. Edit SERVER_BASE_URL and WORKER_TOKEN before running worker." -ForegroundColor Yellow
}

if (-not $SkipInstall) {
    python -m pip install -e ".[test]"
}

if (-not $SkipPlaywrightInstall) {
    python -m playwright install chromium
}

python -m creative_workflow.worker.cli config check

$serverBaseUrl = (Get-Content ".env.worker" | Where-Object { $_ -match "^SERVER_BASE_URL=" } | Select-Object -First 1) -replace "^SERVER_BASE_URL=", ""
$uiUrl = $serverBaseUrl -replace ":8000$", ":8501"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\create_designer_shortcuts.ps1" -AppRoot $AppRoot -UiUrl $uiUrl

Write-Host ""
Write-Host "Designer checkout updated. Start the worker with:" -ForegroundColor Green
Write-Host "  cd $AppRoot"
Write-Host "  python -m creative_workflow.worker.cli run"
