"""Worker configuration loading for the designer laptop."""

from dataclasses import dataclass
from pathlib import Path
import os


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
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
    playwright_profile_root: Path
    playwright_browser_channel: str | None
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
            playwright_profile_root=Path(os.getenv("PLAYWRIGHT_PROFILE_ROOT", "C:/creative-workflow-worker/profiles")),
            playwright_browser_channel=os.getenv("PLAYWRIGHT_BROWSER_CHANNEL") or None,
            worker_capabilities=[
                item.strip()
                for item in os.getenv(
                    "WORKER_CAPABILITIES",
                    "browser.playwright,browser.gemini,browser.freepik,agent.chat",
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
        if self.playwright_browser_channel and self.playwright_browser_channel not in {"chrome", "msedge"}:
            errors.append("PLAYWRIGHT_BROWSER_CHANNEL must be chrome or msedge when set.")
        return errors
