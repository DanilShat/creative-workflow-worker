<#
.SYNOPSIS
  Register the creative-workflow MCP server with Claude Desktop.

.DESCRIPTION
  Writes (or updates) %APPDATA%\Claude\claude_desktop_config.json so that
  Claude Desktop spawns the creative-workflow MCP server over stdio.
  Backs up any existing config before modifying it. Idempotent — re-running
  replaces only the 'creative-workflow' entry under mcpServers.

.PARAMETER PythonExe
  Path to the Python interpreter that has creative-workflow-worker
  installed (editable or wheel). Defaults to the active 'python' on PATH.

.PARAMETER EnvFile
  Absolute path to the worker .env file (.env.worker). The MCP server
  reads SERVER_BASE_URL and WORKER_TOKEN from it.

.EXAMPLE
  .\register_mcp_with_claude_desktop.ps1 `
    -PythonExe "C:\Users\me\.venv\Scripts\python.exe" `
    -EnvFile "C:\creative-workflow-worker\app\.env.worker"
#>

param(
  [string]$PythonExe = "python",
  [Parameter(Mandatory = $true)][string]$EnvFile
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
  throw "EnvFile not found: $EnvFile"
}

if ($PythonExe -ne "python" -and -not (Test-Path $PythonExe)) {
  throw "PythonExe not found: $PythonExe"
}

$configDir = Join-Path $env:APPDATA "Claude"
$configPath = Join-Path $configDir "claude_desktop_config.json"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null

$config = [ordered]@{ mcpServers = [ordered]@{} }
if (Test-Path $configPath) {
  $backup = "$configPath.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
  Copy-Item $configPath $backup
  Write-Host "Backed up existing config to $backup"

  try {
    $existing = Get-Content $configPath -Raw | ConvertFrom-Json -AsHashtable -ErrorAction Stop
    if ($existing) { $config = $existing }
    if (-not $config.ContainsKey("mcpServers")) { $config["mcpServers"] = [ordered]@{} }
  } catch {
    Write-Warning "Existing config is not valid JSON; rewriting."
  }
}

$config["mcpServers"]["creative-workflow"] = [ordered]@{
  command = $PythonExe
  args    = @("-m", "creative_workflow.worker.mcp.server")
  env     = [ordered]@{
    CREATIVE_WORKFLOW_ENV_FILE = $EnvFile
  }
}

$json = $config | ConvertTo-Json -Depth 8
Set-Content -Path $configPath -Value $json -Encoding utf8

Write-Host ""
Write-Host "Registered creative-workflow MCP server."
Write-Host "Config: $configPath"
Write-Host "Restart Claude Desktop to pick up the new server."
