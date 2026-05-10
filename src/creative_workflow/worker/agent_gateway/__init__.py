"""Local agent gateway: HTTP service for the in-app DCC panel(s).

The Photoshop UXP panel (and later other DCC panels) talks to this
gateway over localhost. The gateway routes real messages to Ollama first
and escalates to Claude only when the local model flags a request as
needing stronger creative reasoning.

Returned actions stay inside a typed allowlist before Photoshop can
execute them.
"""

from creative_workflow.worker.agent_gateway.server import build_app, run

__all__ = ["build_app", "run"]
