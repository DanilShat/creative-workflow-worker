"""LLM clients for the agent gateway.

Ollama (gemma3n:e2b) is asked first; Claude is the escalation surface.
Mechanical requests use the configured Sonnet model, and creative
requests use the configured Opus model. Both clients return the same
:class:`LLMEnvelope` so the router doesn't care which one answered.
"""

from creative_workflow.worker.agent_gateway.llm.envelope import LLMEnvelope
from creative_workflow.worker.agent_gateway.llm.claude_client import ClaudeClient
from creative_workflow.worker.agent_gateway.llm.ollama_client import OllamaClient

__all__ = ["LLMEnvelope", "ClaudeClient", "OllamaClient"]
