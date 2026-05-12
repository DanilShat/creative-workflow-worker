# Agent Manifest - Worker Repo

Read this before implementing Claude, browser-assisted, Photoshop, or After
Effects features in this repo.

Canonical design source:

```text
../creative_workflow_docs_library/CLAUDE_CODE_COLLABORATION_MANIFEST.md
```

## Worker responsibilities

The worker repo owns designer-laptop execution:

- worker registration, heartbeat, polling, and job claiming
- Playwright browser flows
- artifact download/upload
- local browser/DCC capability reporting
- local Claude Code CLI, Codex CLI, MCP server, and DCC bridges

Claude can help operate local tools, but execution results still flow through
the worker protocol.

## Current Gate B worker additions

1. Local MCP server process for Claude Desktop.
2. Read-side tools:
   - `get_context`
   - `list_artifacts`
3. Write/request tools:
   - `request_review`
   - `submit_browser_job`
   - `submit_aftereffects_render`
4. Local Photoshop agent gateway:
   - FastAPI `/health` and `/chat`
   - operator Ollama for routine chat
   - Claude Code/Codex escalation through local subscription CLIs
   - typed action allowlist
5. Photoshop UXP panel skeleton.
6. After Effects `aerender.exe` bridge for named comp renders.

Still not complete:

- Claude-assisted visible-browser executor for already trusted browser sessions.
- Live Codex CLI browser validation on the designer laptop after login.
- Real Photoshop execution validation on a designer laptop with Photoshop installed.
- Real After Effects validation with a sample `.aep` project and `AERENDER_EXE`.
- Capability reporting that distinguishes configured bridges from installed code.

## Browser-assisted mode

This mode exists for provider accounts that cannot log in through Playwright
because Google/Freepik treat the Playwright profile as a new device.

Allowed:

- visible browser actions under designer supervision
- prompt entry and generation controls
- downloads that are then uploaded through worker artifacts

Disallowed:

- cookie/session extraction
- hidden auth bypass
- direct provider API scraping
- purchase/billing/account changes without explicit confirmation

## Photoshop and After Effects

Photoshop and After Effects must remain typed action bridges:

- Claude requests an action.
- The worker validates schema and capability.
- The bridge executes reviewed local code.
- The worker uploads outputs and status.

Claude must not send arbitrary UXP, ExtendScript, shell, or Python code into
Adobe apps.

## Handoff Log

### 2026-05-10 - Codex
- Context: Added worker-side manifest for future Claude/browser/DCC work.
- Decision: MCP and desktop/browser/DCC tools belong on the designer laptop,
  but they still report through the worker/server protocol.
- Files changed: `AGENT_MANIFEST.md`, README pointer.
- Tests run: documentation-only change; no tests required.
- Open questions: final MCP package choice and exact local bridge transports
  for Photoshop and After Effects.

### 2026-05-10 - Claude Code + Codex
- Context: Claude Code added the Gate B worker surface; Codex reviewed and
  closed the missing B3 MCP registration.
- Decision: B3 is code-complete for `Claude MCP -> submit_aftereffects_render
  -> aerender.exe`, but not live-accepted until a real After Effects install
  renders a sample comp.
- Files changed: MCP server/tools/tests, agent gateway, Photoshop panel docs,
  AE runner.
- Tests run: worker pytest suite.
- Open questions: exact sample `.aep` fixture and designer laptop AE output
  module naming.

### 2026-05-12 - Codex
- Context: Added worker-local agent runtime for `claude_cli` and `codex_cli`,
  plus `designer_agent_chat` job execution.
- Decision: Subscription CLI login is the worker boundary. Operator-local
  Ollama handles routine chat; browser/creative requests become worker jobs and
  route to the least-used available CLI agent.
- Files changed: agent runtime modules, worker coordinator, CLI status command,
  setup script, README, `.env.worker.example`.
- Tests run: targeted worker unit and integration tests.
- Open questions: verify the installed Claude Code and Codex CLI non-interactive
  command flags on the actual designer laptop.
