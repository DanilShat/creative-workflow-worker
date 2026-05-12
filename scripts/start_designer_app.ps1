param(
    [string]$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

$ErrorActionPreference = "Stop"

function Get-EnvValue {
    param(
        [string]$Path,
        [string]$Name
    )
    if (-not (Test-Path $Path)) {
        return $null
    }
    $line = Get-Content $Path | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
    if (-not $line) {
        return $null
    }
    return ($line -replace "^$Name=", "").Trim().Trim('"')
}

$AppRoot = Resolve-Path $AppRoot
Set-Location $AppRoot

Write-Host "Creative Workflow designer app" -ForegroundColor Cyan
Write-Host "App root: $AppRoot"

if (-not (Test-Path ".env.worker")) {
    Copy-Item ".env.worker.example" ".env.worker"
    Write-Host "Created .env.worker. Fill SERVER_BASE_URL and WORKER_TOKEN, then run this shortcut again." -ForegroundColor Yellow
    notepad ".env.worker"
    return
}

$serverBaseUrl = Get-EnvValue ".env.worker" "SERVER_BASE_URL"
if ($serverBaseUrl) {
    $uiUrl = $serverBaseUrl -replace ":8000$", ":8501"
    Write-Host "Opening operator UI: $uiUrl"
    Start-Process $uiUrl
}

python -m creative_workflow.worker.cli config check
Write-Host ""
python -m creative_workflow.worker.cli agent status
Write-Host ""
Write-Host "Starting worker. Keep this window open while using Creative Workflow." -ForegroundColor Green
python -m creative_workflow.worker.cli run
