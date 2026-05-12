"""Designer worker CLI."""

import shutil
import socket

import httpx
import typer

from creative_workflow.worker.agent_runtime.job_executor import _default_backends
from creative_workflow.worker.browser.profiles import ProfileManager
from creative_workflow.worker.config import WorkerSettings
from creative_workflow.worker.runtime.coordinator import WorkerCoordinator

app = typer.Typer(help="Designer worker commands.")
profile_app = typer.Typer(help="Browser profile commands.")
config_app = typer.Typer(help="Configuration commands.")
agent_app = typer.Typer(help="Local Claude Code and Codex CLI checks.")
app.add_typer(profile_app, name="profile")
app.add_typer(config_app, name="config")
app.add_typer(agent_app, name="agent")


def _settings() -> WorkerSettings:
    return WorkerSettings.load()


@config_app.command("check")
def config_check():
    settings = _settings()
    errors = settings.validate()
    if errors:
        for error in errors:
            typer.echo(f"FAIL: {error}")
        raise typer.Exit(1)
    settings.worker_temp_root.mkdir(parents=True, exist_ok=True)
    settings.playwright_profile_root.mkdir(parents=True, exist_ok=True)
    typer.echo("OK: worker configuration is valid.")
    typer.echo(f"Worker ID: {settings.worker_id}")
    typer.echo(f"Server: {settings.server_base_url}")
    typer.echo(f"Capabilities: {', '.join(settings.worker_capabilities)}")


@app.command("healthcheck")
def healthcheck():
    settings = _settings()
    try:
        response = httpx.get(f"{settings.server_base_url}/api/v1/health", timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        typer.echo(f"FAIL: cannot reach server: {exc}")
        raise typer.Exit(1) from exc
    if shutil.which("python") is None:
        typer.echo("FAIL: python executable not found on PATH.")
        raise typer.Exit(1)
    typer.echo("OK: worker can reach server and local Python runtime.")
    typer.echo(f"Hostname: {socket.gethostname()}")


@app.command("run")
def run():
    settings = _settings()
    errors = settings.validate()
    if errors:
        for error in errors:
            typer.echo(f"FAIL: {error}")
        raise typer.Exit(1)
    WorkerCoordinator(settings).run_forever()


@profile_app.command("setup")
def profile_setup(service: str):
    status = ProfileManager(_settings().playwright_profile_root).setup_profile(service)
    typer.echo(f"{service}: {status.value}")


@profile_app.command("status")
def profile_status(service: str | None = None):
    manager = ProfileManager(_settings().playwright_profile_root)
    if service:
        typer.echo(f"{service}: {manager.check_status(service).value}")
    else:
        for name in manager.list_profiles():
            typer.echo(f"{name}: {manager.check_status(name).value}")


@profile_app.command("list")
def profiles_list():
    for name, status in ProfileManager(_settings().playwright_profile_root).list_profiles().items():
        typer.echo(f"{name}: {status}")


@agent_app.command("status")
def agent_status():
    """Show local agent readiness without requiring API keys."""

    _settings()
    for backend in _default_backends():
        status = backend.probe()
        state = "ready" if status.available else "unavailable"
        detail = f" ({status.reason})" if status.reason else ""
        version = f" version={status.version}" if status.version else ""
        typer.echo(f"{status.name}: {state}; installed={status.installed}; logged_in={status.logged_in}{version}{detail}")


if __name__ == "__main__":
    app()
