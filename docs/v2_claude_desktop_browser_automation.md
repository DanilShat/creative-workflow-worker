# V2 Claude Desktop Browser Automation Note

## Decision

Freepik login through Google can require existing-device approval. Gate A
Playwright persistent profiles are still valid for accounts that can log in
inside the worker browser, but they are not the right mechanism for an account
that must use an already trusted daily browser session.

For V2, implement a Claude Desktop / Claude Code assisted desktop-browser
executor on the designer laptop. That executor should operate the already open
normal browser window through user-visible UI actions after designer approval,
instead of trying to clone cookies or force Google OAuth through a new browser
profile.

## Why

- Playwright opens an isolated browser context, which can look like a new
  device to Google/Freepik.
- Copying Chrome profiles is fragile because encrypted cookies, storage, and
  provider risk checks may not survive a clone.
- Claude desktop UI automation can work with the browser session the designer
  already trusts, which matches the actual operational constraint.

## V2 Shape

- Server still owns tasks, state, artifacts, review, and retry.
- Designer worker exposes allowlisted desktop-browser actions.
- Claude receives a server-generated task handoff and can click/type/read the
  visible browser only with designer supervision.
- Generated files are still uploaded through the worker artifact path.
- This mode must be clearly labeled as desktop-assisted, not Playwright live
  browser acceptance.

## Gate A Status

Do not keep debugging Chrome cookie clones as part of Gate A. Clean the
experimental worker profile copies and keep the designer laptop ready for the
worker/server protocol. Freepik through the already authenticated daily browser
belongs to V2.
