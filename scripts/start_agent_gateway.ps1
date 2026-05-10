<#
.SYNOPSIS
  Start the local agent gateway used by the Photoshop UXP panel.

.DESCRIPTION
  Runs the FastAPI gateway on http://127.0.0.1:8765 (override with -Host /
  -Port). The Photoshop panel calls /health and /chat on this address. In
  B2.2+ the /chat endpoint routes to Ollama first and escalates to Claude
  when the local model asks for help.

.PARAMETER PythonExe
  Path to the Python interpreter that has creative-workflow-worker
  installed. Defaults to 'python' on PATH.

.PARAMETER GatewayHost
  Bind address. Default 127.0.0.1 (localhost-only is the secure default
  because the gateway exposes raw LLM/agent capabilities).

.PARAMETER Port
  TCP port. Default 8765.

.EXAMPLE
  .\start_agent_gateway.ps1
  .\start_agent_gateway.ps1 -PythonExe "C:\path\to\.venv\Scripts\python.exe"
#>

param(
  [string]$PythonExe = "python",
  [string]$GatewayHost = "127.0.0.1",
  [int]$Port = 8765
)

$ErrorActionPreference = "Stop"

if ($PythonExe -ne "python" -and -not (Test-Path $PythonExe)) {
  throw "PythonExe not found: $PythonExe"
}

$env:AGENT_GATEWAY_HOST = $GatewayHost
$env:AGENT_GATEWAY_PORT = "$Port"

Write-Host "Starting creative-workflow-gateway on http://${GatewayHost}:${Port}"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

& $PythonExe -m creative_workflow.worker.agent_gateway.server
