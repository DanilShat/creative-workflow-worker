"""Worker local state file.

This file is diagnostic state, not authoritative task state. The server remains
the source of truth for jobs and workflow transitions.
"""

from pathlib import Path
import json

from pydantic import BaseModel, Field


class WorkerLocalState(BaseModel):
    worker_id: str
    status: str = "starting"
    active_job_id: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class LocalStateStore:
    def __init__(self, path: Path):
        self.path = path

    def save(self, state: WorkerLocalState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def load(self, worker_id: str) -> WorkerLocalState:
        if not self.path.exists():
            return WorkerLocalState(worker_id=worker_id)
        return WorkerLocalState.model_validate(json.loads(self.path.read_text(encoding="utf-8")))

