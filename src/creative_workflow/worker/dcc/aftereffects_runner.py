"""After Effects render runner — wraps the ``aerender.exe`` CLI.

Headless render path for the chat-driven AE workflow (B3). The designer
sets up an AE project once with the comps they care about and the right
output module. Claude Desktop kicks off renders via the MCP tool, the
tool calls into this runner, the runner spawns ``aerender`` and reports
back when the file is ready.

Asset overrides are intentionally out of scope for B3.0 — designer-side
project conventions handle that. B3.1 will add ExtendScript hooks for
property overrides.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_OUTPUT_MODULE = "Lossless"


class AERenderError(RuntimeError):
    """Raised when the aerender invocation fails."""


@dataclass
class AERenderRequest:
    project_path: Path
    comp_name: str
    output_path: Path
    output_module: str = DEFAULT_OUTPUT_MODULE
    extra_args: list[str] = field(default_factory=list)


@dataclass
class AERenderResult:
    output_path: Path
    duration_s: float
    stdout_tail: str
    stderr_tail: str


def _resolve_aerender_exe() -> Path:
    explicit = os.getenv("AERENDER_EXE")
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise AERenderError(f"AERENDER_EXE points to a missing file: {p}")
        return p

    on_path = shutil.which("aerender")
    if on_path:
        return Path(on_path)

    candidates = [
        Path(r"C:/Program Files/Adobe/Adobe After Effects 2026/Support Files/aerender.exe"),
        Path(r"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe"),
        Path(r"C:/Program Files/Adobe/Adobe After Effects 2024/Support Files/aerender.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return c

    raise AERenderError(
        "Could not locate aerender.exe. Set AERENDER_EXE in .env.worker to "
        "the full path of your After Effects installation, e.g. "
        '"C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe".'
    )


async def run_aerender(req: AERenderRequest) -> AERenderResult:
    """Spawn aerender for a single comp render and wait for it to finish.

    Stdout and stderr are buffered and the last few KB are returned for
    diagnostics. Designers don't read them, but Claude can summarize the
    failure case in chat without us having to teach it the AE error
    vocabulary.
    """

    exe = _resolve_aerender_exe()
    if not req.project_path.is_file():
        raise AERenderError(f"Project not found: {req.project_path}")
    req.output_path.parent.mkdir(parents=True, exist_ok=True)

    args: list[str] = [
        str(exe),
        "-project", str(req.project_path),
        "-comp", req.comp_name,
        "-output", str(req.output_path),
        "-OMtemplate", req.output_module,
        *req.extra_args,
    ]

    started = asyncio.get_event_loop().time()
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    duration = asyncio.get_event_loop().time() - started

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")

    if proc.returncode != 0:
        raise AERenderError(
            f"aerender failed with exit code {proc.returncode}.\n"
            f"--- stderr (tail) ---\n{stderr[-2048:]}"
        )

    if not req.output_path.is_file():
        raise AERenderError(
            "aerender returned exit code 0 but the output file was not "
            f"written: {req.output_path}.\n"
            "Check the comp's output module template in After Effects — "
            "some templates write to a different filename than expected."
        )

    return AERenderResult(
        output_path=req.output_path,
        duration_s=duration,
        stdout_tail=stdout[-2048:],
        stderr_tail=stderr[-2048:],
    )
