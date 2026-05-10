param(
    [string]$SourceUserDataDir = "$env:LOCALAPPDATA\Google\Chrome\User Data",
    [string]$ProfileDirectory = "Default",
    [string]$TargetProfileRoot = "",
    [string[]]$Services = @("gemini", "freepik"),
    [switch]$StopChrome
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $TargetProfileRoot) {
    $TargetProfileRoot = Join-Path $RepoRoot "runtime_data\profiles"
}

function Invoke-RobocopyChecked {
    param(
        [string]$Source,
        [string]$Destination
    )
    $excludeDirs = @(
        "Cache",
        "Code Cache",
        "GPUCache",
        "GrShaderCache",
        "ShaderCache",
        "Service Worker\CacheStorage",
        "Crashpad",
        "BrowserMetrics"
    )
    $excludeFiles = @(
        "SingletonCookie",
        "SingletonLock",
        "SingletonSocket",
        "lockfile",
        "*.tmp"
    )
    $args = @(
        $Source,
        $Destination,
        "/MIR",
        "/R:2",
        "/W:2",
        "/XD"
    ) + $excludeDirs + @("/XF") + $excludeFiles

    & robocopy @args | Out-Host
    $exitCode = $LASTEXITCODE
    if ($exitCode -gt 7) {
        throw "robocopy failed with exit code $exitCode"
    }
}

if (-not (Test-Path $SourceUserDataDir)) {
    throw "Chrome user data directory was not found: $SourceUserDataDir"
}

$sourceProfile = Join-Path $SourceUserDataDir $ProfileDirectory
if (-not (Test-Path $sourceProfile)) {
    throw "Chrome profile directory was not found: $sourceProfile"
}

$runningChrome = Get-Process chrome -ErrorAction SilentlyContinue
if ($runningChrome -and -not $StopChrome) {
    Write-Host "Chrome is running. Close all Chrome windows first, or rerun with -StopChrome." -ForegroundColor Yellow
    throw "Chrome must be closed so profile cookies and databases copy consistently."
}

if ($runningChrome -and $StopChrome) {
    Stop-Process -Name chrome -Force
    Start-Sleep -Seconds 2
}

foreach ($service in $Services) {
    $target = Join-Path $TargetProfileRoot $service
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Write-Host ""
    Write-Host "Copying Chrome profile to $target" -ForegroundColor Cyan
    Invoke-RobocopyChecked -Source $SourceUserDataDir -Destination $target
    $targetProfile = Join-Path $target $ProfileDirectory
    if (-not (Test-Path $targetProfile)) {
        Write-Host "Profile folder was not present after full copy; copying $ProfileDirectory directly." -ForegroundColor Yellow
        Invoke-RobocopyChecked -Source $sourceProfile -Destination $targetProfile
    }
}

$envPath = Join-Path $RepoRoot ".env.worker"
if (Test-Path $envPath) {
    $lines = Get-Content $envPath
    if ($lines -match "^PLAYWRIGHT_BROWSER_CHANNEL=") {
        $lines = $lines | ForEach-Object {
            if ($_ -match "^PLAYWRIGHT_BROWSER_CHANNEL=") { "PLAYWRIGHT_BROWSER_CHANNEL=chrome" } else { $_ }
        }
    } else {
        $lines += "PLAYWRIGHT_BROWSER_CHANNEL=chrome"
    }
    if ($lines -match "^PLAYWRIGHT_CHROME_PROFILE_DIRECTORY=") {
        $lines = $lines | ForEach-Object {
            if ($_ -match "^PLAYWRIGHT_CHROME_PROFILE_DIRECTORY=") { "PLAYWRIGHT_CHROME_PROFILE_DIRECTORY=$ProfileDirectory" } else { $_ }
        }
    } else {
        $lines += "PLAYWRIGHT_CHROME_PROFILE_DIRECTORY=$ProfileDirectory"
    }
    Set-Content -Path $envPath -Value $lines -Encoding UTF8
    Write-Host ""
    Write-Host "Updated .env.worker to use Chrome profile directory '$ProfileDirectory'." -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Run these checks next:"
Write-Host "  python -m creative_workflow.worker.cli profile status"
Write-Host "  python -m creative_workflow.worker.cli profile setup freepik"
