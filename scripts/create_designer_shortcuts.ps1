param(
    [string]$AppRoot = "C:\creative-workflow-worker\app",
    [string]$UiUrl = "http://192.168.1.124:8501"
)

$ErrorActionPreference = "Stop"

$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

$workerShortcut = $shell.CreateShortcut((Join-Path $desktop "Creative Workflow Worker.lnk"))
$workerShortcut.TargetPath = "powershell.exe"
$workerShortcut.Arguments = "-NoExit -ExecutionPolicy Bypass -Command `"cd '$AppRoot'; python -m creative_workflow.worker.cli run`""
$workerShortcut.WorkingDirectory = $AppRoot
$workerShortcut.Description = "Start the Creative Workflow designer worker"
$workerShortcut.Save()

$uiShortcutPath = Join-Path $desktop "Creative Workflow UI.url"
Set-Content -Path $uiShortcutPath -Value @(
    "[InternetShortcut]",
    "URL=$UiUrl"
) -Encoding ASCII

Write-Host "Created desktop shortcuts:" -ForegroundColor Green
Write-Host "  Creative Workflow Worker.lnk"
Write-Host "  Creative Workflow UI.url"
