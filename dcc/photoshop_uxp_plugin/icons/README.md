# Plugin icons

Photoshop expects two PNGs here:

- `icon-light.png` — used in light themes (`lightest`, `light`, `medium`)
- `icon-dark.png`  — used in dark themes (`dark`, `darkest`)

Both should be **23×23 px** at 1× and **46×46 px** at 2×. Adobe will
auto-pick the right size at the right scale.

If these files are missing the plugin still loads; the panel just falls
back to a generic placeholder icon in the Plugins panel list. Drop real
PNGs here when you have them — no rebuild needed.
