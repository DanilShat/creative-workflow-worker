"""Local agent backends used by the designer worker.

The worker talks to three local tools:
- Ollama for cheap routine reasoning on the designer laptop.
- Claude Code CLI for subscription-account escalation.
- Codex CLI for subscription-account escalation, including browser-capable work.

These are intentionally CLI/local integrations, not API-key integrations. The
operator only sees job state and final text; account login stays on the
designer laptop where the tools are installed.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import os
import subprocess
from typing import Sequence

import httpx

from creative_workflow.worker.agent_runtime.schemas import (
    AgentBackendStatus,
    AgentChatRequest,
    AgentCommandResult,
    AgentName,
)


CommandRunner = Callable[[Sequence[str], str | None, int], tuple[int, str, str]]


def default_runner(args: Sequence[str], input_text: str | None = None, timeout_s: int = 120) -> tuple[int, str, str]:
    """Run a local subscription CLI and return process-style output.

    The runner is injectable so tests can prove command construction without
    requiring Claude Code or Codex to be installed in CI.
    """

    try:
        completed = subprocess.run(
            list(args),
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return 124, stdout, stderr or "command timed out"
    return completed.returncode, completed.stdout, completed.stderr


class CliAgentBackend:
    """Backend for local subscription CLIs such as `claude` and `codex`."""

    def __init__(
        self,
        name: AgentName,
        executable: str,
        runner: CommandRunner = default_runner,
        version_args: Sequence[str] = ("--version",),
        status_args: Sequence[str] = ("status",),
        chat_args: Sequence[str] = (),
        timeout_s: int = 120,
    ) -> None:
        self.name = name
        self.executable = executable
        self.runner = runner
        self.version_args = tuple(version_args)
        self.status_args = tuple(status_args)
        self.chat_args = tuple(chat_args)
        self.timeout_s = timeout_s

    def probe(self) -> AgentBackendStatus:
        version_code, version_out, version_err = self.runner(
            (self.executable, *self.version_args),
            None,
            30,
        )
        if version_code == 127:
            return AgentBackendStatus(
                name=self.name,
                available=False,
                installed=False,
                logged_in=False,
                reason=(version_err or f"{self._display_name()} not found on PATH.").strip(),
                supports_browser=self._supports_browser(),
            )
        if version_code != 0:
            return AgentBackendStatus(
                name=self.name,
                available=False,
                installed=False,
                logged_in=False,
                reason=(version_err or version_out or f"{self._display_name()} version check failed.").strip(),
                supports_browser=self._supports_browser(),
            )

        version = (version_out or version_err).strip().splitlines()[0] if (version_out or version_err).strip() else None
        if self.status_args:
            status_code, status_out, status_err = self.runner((self.executable, *self.status_args), None, 30)
            status_text = (status_out + "\n" + status_err).strip()
            if status_code != 0 and self._looks_like_login_problem(status_text):
                return AgentBackendStatus(
                    name=self.name,
                    available=False,
                    installed=True,
                    logged_in=False,
                    reason=status_text or f"{self._display_name()} is installed but not logged in.",
                    version=version,
                    supports_browser=self._supports_browser(),
                )
            if status_code != 0 and self._looks_like_missing_status_command(status_text):
                return AgentBackendStatus(
                    name=self.name,
                    available=True,
                    installed=True,
                    logged_in=True,
                    version=version,
                    supports_browser=self._supports_browser(),
                )
            if status_code != 0 and status_text:
                # Some CLIs do not expose a status command yet. If the command
                # exists but fails for a non-auth reason, surface the failure so
                # setup is explicit instead of pretending the agent is usable.
                return AgentBackendStatus(
                    name=self.name,
                    available=False,
                    installed=True,
                    logged_in=True,
                    reason=status_text,
                    version=version,
                    supports_browser=self._supports_browser(),
                )

        return AgentBackendStatus(
            name=self.name,
            available=True,
            installed=True,
            logged_in=True,
            version=version,
            supports_browser=self._supports_browser(),
        )

    def chat(self, request: AgentChatRequest) -> AgentCommandResult:
        prompt = self._prompt_for(request)
        code, stdout, stderr = self.runner((self.executable, *self.chat_args), prompt, self.timeout_s)
        if code != 0:
            raise RuntimeError((stderr or stdout or f"{self._display_name()} exited with code {code}.").strip())
        text = (stdout or stderr).strip()
        return AgentCommandResult(agent=self.name, text=text, routed_to=self.name, raw_output=(stdout + stderr).strip())

    def _prompt_for(self, request: AgentChatRequest) -> str:
        context = json.dumps(request.context, ensure_ascii=True, indent=2) if request.context else "{}"
        return (
            "You are running inside Creative Workflow on the designer laptop.\n"
            "Use your local subscription CLI session. Do not ask for API keys.\n"
            f"Task ID: {request.task_id or 'none'}\n"
            f"Context JSON:\n{context}\n\n"
            f"Designer message:\n{request.message}\n"
        )

    def _display_name(self) -> str:
        return {"claude_cli": "Claude Code CLI", "codex_cli": "Codex CLI"}.get(self.name, self.name)

    def _supports_browser(self) -> bool:
        return self.name in {"claude_cli", "codex_cli"}

    @staticmethod
    def _looks_like_login_problem(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in ("login", "log in", "logged in", "auth", "authenticate", "not logged"))

    @staticmethod
    def _looks_like_missing_status_command(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in ("unknown command", "unknown subcommand", "unrecognized subcommand", "invalid command"))


class LocalOllamaBackend:
    """Backend for routine local reasoning through an Ollama-compatible server."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        healthcheck: Callable[[], tuple[bool, str | None]] | None = None,
        generate: Callable[[str], str] | None = None,
    ) -> None:
        self.name: AgentName = "local_ollama"
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL") or "gemma3n:e2b"
        self._healthcheck = healthcheck or self._default_healthcheck
        self._generate = generate or self._default_generate

    def probe(self) -> AgentBackendStatus:
        ok, reason = self._healthcheck()
        return AgentBackendStatus(
            name=self.name,
            available=ok,
            installed=ok,
            logged_in=True,
            reason=None if ok else reason,
            version=self.model,
            supports_browser=False,
        )

    def chat(self, request: AgentChatRequest) -> AgentCommandResult:
        prompt = (
            "You are Creative Workflow's local reasoning model. Answer concise, actionable operator questions.\n"
            f"Task ID: {request.task_id or 'none'}\n"
            f"Message:\n{request.message}\n"
        )
        text = self._generate(prompt).strip()
        return AgentCommandResult(agent=self.name, text=text, routed_to=self.name, raw_output=text)

    def _default_healthcheck(self) -> tuple[bool, str | None]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return False, str(exc)
        return True, None

    def _default_generate(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("response") or "")
