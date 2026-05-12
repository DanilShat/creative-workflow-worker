"""Small local usage ledger used to spread work across CLI agents."""

from __future__ import annotations

import json
from pathlib import Path

from creative_workflow.worker.agent_runtime.schemas import AgentName, UsageEntry


class UsageLedger:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict[AgentName, UsageEntry]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {name: UsageEntry.model_validate(value) for name, value in data.items()}

    def score(self, name: AgentName) -> tuple[int, int]:
        entry = self.load().get(name, UsageEntry())
        return (entry.successes + entry.failures, entry.failures)

    def record_success(self, name: AgentName) -> None:
        usage = self.load()
        entry = usage.get(name, UsageEntry())
        entry.successes += 1
        usage[name] = entry
        self._save(usage)

    def record_failure(self, name: AgentName) -> None:
        usage = self.load()
        entry = usage.get(name, UsageEntry())
        entry.failures += 1
        usage[name] = entry
        self._save(usage)

    def _save(self, usage: dict[AgentName, UsageEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({name: entry.model_dump() for name, entry in usage.items()}, indent=2),
            encoding="utf-8",
        )
