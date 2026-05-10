# Creative Workflow Assistant — Photoshop UXP plugin

This is the panel that lives inside Photoshop. It gives designers a chat
input where they can ask for small tweaks ("crop tighter on the right",
"darken the sky") while editing.

## Status

- **B2.1:** panel UI and gateway round-trip.
- **B2.2:** local Ollama-first routing, Claude escalation, and typed
  allowlisted bridge actions (`crop`, `export`, `get_context`).
- **B2.3 (later):** plugin packaging (`.ccx`), signing, distribution.

## Files

| | |
|---|---|
| `manifest.json` | UXP plugin manifest (id, host, panel entry, network permissions) |
| `index.html`    | Panel shell — header, doc-context strip, log, composer |
| `panel.css`     | Styling — dark theme matched to Photoshop |
| `panel.js`      | Panel logic — calls gateway, renders messages |
| `icons/`        | Plugin icons (light + dark) |

## Loading in Photoshop (Develop mode)

Designer setup is documented at
`creative_workflow_docs_library/designer_workspace/photoshop_panel_setup.md`.

Short version:

1. Install Adobe **UXP Developer Tool** (free, separate from Photoshop).
2. In UDT click **Add Plugin**, point it at `manifest.json` in this folder.
3. Click **Load** → Photoshop opens the panel under Plugins → Creative
   Workflow Assistant.
4. Make sure the gateway is running (`creative-workflow-gateway` console
   script or `scripts/start_agent_gateway.ps1`).

## Architecture

See `creative_workflow_docs_library/codex/50_gate_b_b2_photoshop_panel_spec.md`
for the full spec and `creative_workflow_docs_library/docs/diagrams/gate_b2_architecture.svg`
for the diagram.
