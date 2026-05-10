param(
    [ValidateSet("install", "test", "lint", "run")]
    [string]$Task = "test"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path $PSScriptRoot
Set-Location $RepoRoot

switch ($Task) {
    "install" {
        python -m pip install -e ".[test]"
        python -m playwright install chromium
    }
    "test" {
        python -m pytest tests -q
    }
    "lint" {
        python -m compileall src tests
    }
    "run" {
        python -m creative_workflow.worker.cli run
    }
}
