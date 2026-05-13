"""Worker configuration loading for the designer laptop."""

from dataclasses import dataclass
from pathlib import Path
import os


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        # The designer package carries the operator-generated server URL and
        # worker token. Let that file override stale user-level Windows
        # variables so a previous setup cannot silently point the worker at
        # localhost or an old operator laptop.
        os.environ[key.strip()] = value.strip().strip('"')


@dataclass(frozen=True)
class WorkerSettings:
    server_base_url: str
    worker_id: str
    worker_token: str
    worker_temp_root: Path
    claude_cli_executable: str
    codex_cli_executable: str
    # Retained so coordinator.py ProfileManager construction doesn't break while
    # that path is phased out. V2 browser flows do not use Playwright profiles.
    playwright_profile_root: Path
    worker_capabilities: list[str]
    version: str = "0.1.0"

    @classmethod
    def load(cls, env_file: str | Path | None = ".env.worker") -> "WorkerSettings":
        env_file = os.getenv("CREATIVE_WORKFLOW_ENV_FILE") or env_file
        if env_file:
            _load_env_file(Path(env_file))
        return cls(
            server_base_url=os.getenv("SERVER_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
            worker_id=os.getenv("WORKER_ID", "designer-laptop-01"),
            worker_token=os.getenv("WORKER_TOKEN", ""),
            worker_temp_root=Path(os.getenv("WORKER_TEMP_ROOT", "C:/creative-workflow-worker/temp")),
            claude_cli_executable=os.getenv("CLAUDE_CLI_EXECUTABLE", "claude"),
            codex_cli_executable=os.getenv("CODEX_CLI_EXECUTABLE", "codex"),
            playwright_profile_root=Path(os.getenv("PLAYWRIGHT_PROFILE_ROOT", "C:/creative-workflow-worker/profiles")),
            worker_capabilities=[
                item.strip()
                for item in os.getenv(
                    "WORKER_CAPABILITIES",
                    "browser.desktop,browser.gemini,browser.freepik,agent.chat",
                ).split(",")
                if item.strip()
            ],
        )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.worker_token:
            errors.append("WORKER_TOKEN is required.")
        if not self.worker_id:
            errors.append("WORKER_ID is required.")
        if not self.server_base_url.startswith(("http://", "https://")):
            errors.append("SERVER_BASE_URL must be an HTTP URL.")
        return errors
