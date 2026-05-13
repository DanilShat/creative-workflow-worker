param(
    [string]$AppRoot = "",
    [string]$UiUrl = "http://192.168.1.124:8501"
)

$ErrorActionPreference = "Stop"

if (-not $AppRoot) {
    $AppRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
}

$desktop = [Environment]::GetFolderPath("Desktop")

$launcherPath = Join-Path $desktop "Creative Workflow.cmd"
$startScript = Join-Path $AppRoot "scripts\start_designer_app.ps1"
if (-not (Test-Path $startScript)) {
    throw "Missing designer startup script: $startScript"
}

# Keep one obvious desktop entry point for designers. This launcher opens the
# operator UI and then starts the authenticated worker loop in the same window.
Set-Content -Path $launcherPath -Value @(
    "@echo off",
    "cd /d `"$AppRoot`"",
    "powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File `"$startScript`" -AppRoot `"$AppRoot`""
) -Encoding ASCII

$oldShortcuts = @(
    (Join-Path $desktop "Creative Workflow Worker.lnk"),
    (Join-Path $desktop "Creative Workflow UI.url")
)
foreach ($path in $oldShortcuts) {
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

Write-Host "Created desktop launcher:" -ForegroundColor Green
Write-Host "  Creative Workflow.cmd"
