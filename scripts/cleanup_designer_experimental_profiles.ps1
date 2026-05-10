param(
    [string]$WorkerRoot = "",
    [switch]$Apply,
    [switch]$KeepGeminiProfile,
    [switch]$KeepFreepikProfile,
    [switch]$RemovePlaywrightBrowserCache
)

$ErrorActionPreference = "Stop"

if (-not $WorkerRoot) {
    $WorkerRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
}
$targets = @()

function Set-EnvValue {
    param(
        [string]$Path,
        [string]$Key,
        [string]$Value
    )
    if (-not (Test-Path $Path)) {
        return
    }
    $lines = Get-Content $Path
    $pattern = "^$([regex]::Escape($Key))="
    $updated = $false
    $newLines = foreach ($line in $lines) {
        if ($line -match $pattern) {
            $updated = $true
            "$Key=$Value"
        } else {
            $line
        }
    }
    if (-not $updated) {
        $newLines += "$Key=$Value"
    }
    Set-Content -Path $Path -Value $newLines -Encoding UTF8
}

function Add-WorkerTarget {
    param([string]$Path)
    $fullRoot = [System.IO.Path]::GetFullPath($WorkerRoot).TrimEnd('\')
    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    if (-not ($fullPath -eq $fullRoot -or $fullPath.StartsWith("$fullRoot\", [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Refusing to touch path outside worker root: $fullPath"
    }
    if (Test-Path $fullPath) {
        $script:targets += $fullPath
    }
}

if (-not $KeepFreepikProfile) {
    Add-WorkerTarget (Join-Path $WorkerRoot "runtime_data\profiles\freepik")
}
if (-not $KeepGeminiProfile) {
    Add-WorkerTarget (Join-Path $WorkerRoot "runtime_data\profiles\gemini")
}
Add-WorkerTarget (Join-Path $WorkerRoot "runtime_data\profiles\profile_status.json")
Add-WorkerTarget (Join-Path $WorkerRoot "runtime_data\temp")
Add-WorkerTarget (Join-Path $WorkerRoot "runtime_data\manual_drop")

if ($RemovePlaywrightBrowserCache) {
    $playwrightCache = Join-Path $env:LOCALAPPDATA "ms-playwright"
    if (Test-Path $playwrightCache) {
        $targets += [System.IO.Path]::GetFullPath($playwrightCache).TrimEnd('\')
    }
}

Write-Host "Designer cleanup targets:" -ForegroundColor Cyan
if (-not $targets) {
    Write-Host "  No matching cleanup targets found."
} else {
    foreach ($target in $targets) {
        $size = 0
        if ((Get-Item $target).PSIsContainer) {
            $size = (Get-ChildItem $target -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        } else {
            $size = (Get-Item $target).Length
        }
        Write-Host ("  {0} ({1:N0} bytes)" -f $target, $size)
    }
}

Write-Host ""
if (-not $Apply) {
    Write-Host "Dry run only. Rerun with -Apply to delete these worker-only files." -ForegroundColor Yellow
    exit 0
}

foreach ($target in $targets) {
    Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
    Write-Host "Deleted $target"
}

$envPath = Join-Path (Get-Location) ".env.worker"
if (-not (Test-Path $envPath)) {
    $envPath = Join-Path $WorkerRoot ".env.worker"
}
if (Test-Path $envPath) {
    Set-EnvValue $envPath "PLAYWRIGHT_BROWSER_CHANNEL" "chrome"
    Set-EnvValue $envPath "PLAYWRIGHT_CHROME_PROFILE_DIRECTORY" ""
    Write-Host "Reset experimental Chrome profile-directory setting in $envPath"
}

Write-Host ""
Write-Host "Cleanup complete. The real Chrome profile under AppData was not touched." -ForegroundColor Green
