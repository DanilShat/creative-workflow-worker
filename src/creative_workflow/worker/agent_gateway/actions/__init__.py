"""Action allowlist and validation for the agent gateway.

Wraps the worker's photoshop_actions library, enforces the allowlist
(crop, export, get_context, noop), and validates LLM-supplied params.
The router calls :func:`materialize` to turn a raw LLM envelope into a
concrete :class:`ActionDescriptor` (or a validation_error envelope).
"""

from creative_workflow.worker.agent_gateway.actions.registry import (
    UnknownAction,
    materialize,
)

__all__ = ["UnknownAction", "materialize"]
