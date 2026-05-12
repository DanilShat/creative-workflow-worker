param(
    [switch]$SkipInstall,
    [switch]$SkipProfileSetup
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Body
    )
    Write-Host ""
    Write-Host "== $Title ==" -ForegroundColor Cyan
    & $Body
}

$RepoRoot = Resolve-Path $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml")) -and (Split-Path $RepoRoot -Leaf) -eq "scripts") {
    $RepoRoot = Resolve-Path (Join-Path $RepoRoot "..")
}
Set-Location $RepoRoot

Invoke-Step "Check package files" {
    if (-not (Test-Path "pyproject.toml")) {
        throw "Run this script from the extracted designer_worker_package folder."
    }
    if (-not (Test-Path ".env.worker")) {
        Copy-Item ".env.worker.example" ".env.worker"
        Write-Host "Created .env.worker from example. Edit SERVER_BASE_URL and WORKER_TOKEN before continuing."
        notepad ".env.worker"
    }
}

Invoke-Step "Install worker Python package" {
    if ($SkipInstall) {
        Write-Host "Skipped install because -SkipInstall was provided."
    } else {
        python -m pip install -e ".[test]"
        python -m playwright install chromium
    }
}

Invoke-Step "Check worker configuration" {
    python -m creative_workflow.worker.cli config check
}

Invoke-Step "Check local agent subscriptions" {
    Write-Host "This check does not use API keys. It only reports whether Claude Code CLI and Codex CLI are installed and logged in."
    python -m creative_workflow.worker.cli agent status
}

Invoke-Step "Check server reachability" {
    python -m creative_workflow.worker.cli healthcheck
}

if (-not $SkipProfileSetup) {
    Invoke-Step "Set up Gemini browser profile" {
        Write-Host "A browser will open. Log in to Gemini manually, then return to this terminal and press Enter when asked."
        python -m creative_workflow.worker.cli profile setup gemini
    }
    Invoke-Step "Set up Freepik browser profile" {
        Write-Host "A browser will open. Log in to Freepik manually, then return to this terminal and press Enter when asked."
        python -m creative_workflow.worker.cli profile setup freepik
    }
}

Invoke-Step "Check browser profile status" {
    python -m creative_workflow.worker.cli profile status
}

Invoke-Step "Create desktop shortcuts" {
    $serverBaseUrl = (Get-Content ".env.worker" | Where-Object { $_ -match "^SERVER_BASE_URL=" } | Select-Object -First 1) -replace "^SERVER_BASE_URL=", ""
    $uiUrl = $serverBaseUrl -replace ":8000$", ":8501"
    powershell -ExecutionPolicy Bypass -File ".\scripts\create_designer_shortcuts.ps1" -AppRoot (Get-Location) -UiUrl $uiUrl
}

Write-Host ""
Write-Host "Designer worker setup is ready." -ForegroundColor Green
Write-Host "Start the worker with:"
Write-Host "  python -m creative_workflow.worker.cli run"
Write-Host "Or use the desktop shortcut: Creative Workflow Worker"
