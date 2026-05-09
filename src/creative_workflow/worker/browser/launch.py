"""Shared Playwright launch options for persistent vendor profiles."""

from pathlib import Path
import os


def persistent_context_options(user_data_dir: Path, *, headless: bool = False) -> dict:
    """Return the browser options used by all live Gate A browser flows.

    By default Playwright launches its bundled Chromium. Some OAuth providers,
    including Google, can reject that embedded browser during third-party login.
    PLAYWRIGHT_BROWSER_CHANNEL lets the designer laptop use an installed Chrome
    or Edge while keeping the same isolated automation profile directory.
    """
    options: dict = {
        "user_data_dir": str(user_data_dir),
        "headless": headless,
        "accept_downloads": True,
    }
    channel = os.getenv("PLAYWRIGHT_BROWSER_CHANNEL", "").strip()
    if channel:
        options["channel"] = channel
        options["ignore_default_args"] = ["--enable-automation"]
        args = ["--disable-blink-features=AutomationControlled"]
        profile_directory = os.getenv("PLAYWRIGHT_CHROME_PROFILE_DIRECTORY", "").strip()
        if profile_directory:
            args.append(f"--profile-directory={profile_directory}")
        options["args"] = args
    return options
