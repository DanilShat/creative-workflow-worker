"""FastAPI app factory and CLI entry point for the agent gateway."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from creative_workflow.worker.agent_gateway.router import route_message
from creative_workflow.worker.agent_gateway.schemas import ChatRequest, ChatResponse


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def build_app() -> FastAPI:
    app = FastAPI(
        title="Creative Workflow — Agent Gateway",
        version="0.1.0",
        description=(
            "Local HTTP service that bridges in-app DCC panels (Photoshop "
            "UXP, etc.) to the local Ollama model first, with Claude API "
            "escalation for requests that need stronger creative reasoning."
        ),
    )

    # The UXP panel runs inside Photoshop with an opaque origin that
    # browsers treat as `null`. Allowing localhost-only origins keeps
    # the surface small without breaking the panel.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "null",
            "http://localhost",
            "http://127.0.0.1",
            f"http://localhost:{DEFAULT_PORT}",
            f"http://127.0.0.1:{DEFAULT_PORT}",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "stage": "B2.2"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(req: ChatRequest) -> ChatResponse:
        return await route_message(req)

    return app


def run() -> None:
    """Console-script entry point — `creative-workflow-gateway`."""
    import uvicorn

    host = os.getenv("AGENT_GATEWAY_HOST", DEFAULT_HOST)
    port = int(os.getenv("AGENT_GATEWAY_PORT", str(DEFAULT_PORT)))
    uvicorn.run(
        "creative_workflow.worker.agent_gateway.server:build_app",
        host=host,
        port=port,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":  # pragma: no cover
    run()
