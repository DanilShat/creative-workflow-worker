/* Creative Workflow Assistant — panel logic.
 *
 * Talks to the local agent gateway at http://localhost:8765. The gateway
 * decides whether to answer with the local LLM (Ollama) or escalate to
 * Claude — the panel doesn't care, it just renders the result and runs
 * the typed action the gateway hands back.
 *
 * Action execution lives here in the panel because UXP APIs are only
 * callable from inside the Photoshop runtime. The *logic* of "what is
 * a valid crop, what bounds does '5% off the right' resolve to" lives
 * in the worker's Python code (creative_workflow.worker.dcc.photoshop_actions).
 * The panel is a thin generic dispatcher.
 */

const GATEWAY_BASE = "http://localhost:8765";

const els = {
  status: document.getElementById("status-pill"),
  docName: document.getElementById("doc-name"),
  log: document.getElementById("log"),
  composer: document.getElementById("composer"),
  message: document.getElementById("message"),
  send: document.getElementById("send"),
};

let app = null;
let core = null;
try {
  // require("photoshop") is only available inside the UXP runtime.
  const ps = require("photoshop");
  app = ps.app;
  core = ps.core;
} catch (e) {
  app = null;
  core = null;
}

function setStatus(state, label) {
  els.status.textContent = label;
  els.status.dataset.state = state;
}

function refreshDocContext() {
  if (!app) {
    els.docName.textContent = "panel not running inside Photoshop";
    return null;
  }
  const doc = app.activeDocument;
  if (!doc) {
    els.docName.textContent = "no document open";
    return null;
  }
  els.docName.textContent = doc.name;
  return {
    document_name: doc.name,
    document_width: doc.width,
    document_height: doc.height,
    active_layer: doc.activeLayers && doc.activeLayers[0]
      ? doc.activeLayers[0].name
      : null,
  };
}

function appendMessage(kind, text) {
  const empty = els.log.querySelector(".log-empty");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = `msg msg-${kind}`;
  div.textContent = text;
  els.log.appendChild(div);
  els.log.scrollTop = els.log.scrollHeight;
}

async function checkHealth() {
  try {
    const resp = await fetch(`${GATEWAY_BASE}/health`, { method: "GET" });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    setStatus("online", "online");
  } catch (e) {
    setStatus("offline", "gateway offline");
  }
}

/* ---------- Action execution ---------- */

async function executeAction(action) {
  if (!action || action.status !== "ok") {
    return { ok: false, error: action && action.error ? action.error : "no action" };
  }

  if (!app || !core) {
    return { ok: false, error: "panel not running inside Photoshop" };
  }

  const doc = app.activeDocument;

  switch (action.type) {
    case "noop":
      return { ok: true, data: action.params.echo || {} };

    case "get_context": {
      if (!doc) return { ok: false, error: "no document open" };
      return {
        ok: true,
        data: {
          document_name: doc.name,
          document_width: doc.width,
          document_height: doc.height,
          active_layer: doc.activeLayers && doc.activeLayers[0]
            ? doc.activeLayers[0].name
            : null,
        },
      };
    }

    case "crop": {
      if (!doc) return { ok: false, error: "no document open" };
      const b = action.params.bounds;
      try {
        await core.executeAsModal(
          async () => {
            await doc.crop(
              { left: b.left, top: b.top, right: b.right, bottom: b.bottom },
              0,
              action.params.new_width,
              action.params.new_height
            );
          },
          { commandName: "Creative Workflow — Crop" }
        );
        return { ok: true };
      } catch (e) {
        return { ok: false, error: `crop failed: ${e && e.message ? e.message : e}` };
      }
    }

    case "export": {
      if (!doc) return { ok: false, error: "no document open" };
      const fmt = action.params.format;
      const target = action.params.target_path;
      try {
        await core.executeAsModal(
          async () => {
            // Resolve target inside the plugin's data folder. UXP's
            // localFileSystem requires a token to write outside that;
            // for B2.2 we keep exports in the plugin sandbox and B2.3
            // adds a "save where you'd expect" path.
            const fs = require("uxp").storage.localFileSystem;
            const folder = await fs.getDataFolder();
            const file = await folder.createFile(target.replace(/[\\\/]+/g, "_"), {
              overwrite: true,
            });
            if (fmt === "png") {
              await doc.saveAs.png(file, { compression: 6 });
            } else if (fmt === "jpg") {
              await doc.saveAs.jpg(file, { quality: action.params.quality || 90 });
            } else if (fmt === "webp") {
              // saveAs.webp may not exist on older PS; fall back to JPG with a note.
              if (doc.saveAs.webp) {
                await doc.saveAs.webp(file, { quality: action.params.quality || 90 });
              } else {
                throw new Error("Photoshop version does not support WebP export.");
              }
            }
          },
          { commandName: "Creative Workflow — Export" }
        );
        return { ok: true };
      } catch (e) {
        return { ok: false, error: `export failed: ${e && e.message ? e.message : e}` };
      }
    }

    default:
      return { ok: false, error: `unknown action type: ${action.type}` };
  }
}

/* ---------- Chat lifecycle ---------- */

async function sendMessage(message) {
  const context = refreshDocContext();
  setStatus("thinking", "thinking…");
  els.send.disabled = true;
  try {
    const resp = await fetch(`${GATEWAY_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, context }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const reply = await resp.json();
    const routedBadge = reply.routed_to ? ` [via ${reply.routed_to}]` : "";

    if (reply.kind === "action" && reply.action) {
      appendMessage("agent", (reply.text || "") + routedBadge);
      appendMessage(
        "action",
        `→ ${reply.action.type}(${JSON.stringify(reply.action.params)})`
      );
      const result = await executeAction(reply.action);
      if (result.ok) {
        appendMessage("agent", "✓ done.");
      } else {
        appendMessage("error", `✗ ${result.error}`);
      }
    } else {
      appendMessage("agent", (reply.text || "(empty reply)") + routedBadge);
    }
    setStatus("online", "online");
  } catch (e) {
    appendMessage("error", `gateway error: ${e.message}`);
    setStatus("offline", "gateway offline");
  } finally {
    els.send.disabled = false;
  }
}

els.composer.addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = els.message.value.trim();
  if (!text) return;
  appendMessage("user", text);
  els.message.value = "";
  sendMessage(text);
});

window.addEventListener("focus", refreshDocContext);

refreshDocContext();
checkHealth();
setInterval(checkHealth, 30_000);
