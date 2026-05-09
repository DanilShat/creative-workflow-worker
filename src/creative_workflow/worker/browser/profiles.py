"""Playwright persistent profile lifecycle for vendor accounts."""

from pathlib import Path
import json

from creative_workflow.shared.enums import ProfileStatus
from creative_workflow.worker.browser.launch import persistent_context_options

SERVICE_URLS = {
    "gemini": "https://gemini.google.com/gem/5f69a5afc4b5",
    "freepik": "https://www.freepik.com/pikaso/ai-image-generator",
}


class ProfileManager:
    def __init__(self, profile_root: Path):
        self.profile_root = profile_root
        self.profile_root.mkdir(parents=True, exist_ok=True)
        self.status_path = self.profile_root / "profile_status.json"

    def profile_dir(self, service: str) -> Path:
        return self.profile_root / service

    def list_profiles(self) -> dict[str, str]:
        statuses = self._read_statuses()
        for service in SERVICE_URLS:
            statuses.setdefault(service, ProfileStatus.NEEDS_SETUP.value if not self.profile_dir(service).exists() else ProfileStatus.UNKNOWN.value)
        return statuses

    def get_status(self, service: str) -> ProfileStatus:
        return ProfileStatus(self.list_profiles().get(service, ProfileStatus.UNKNOWN.value))

    def save_status(self, service: str, status: ProfileStatus) -> None:
        statuses = self._read_statuses()
        statuses[service] = status.value
        self.status_path.write_text(json.dumps(statuses, indent=2), encoding="utf-8")

    def setup_profile(self, service: str) -> ProfileStatus:
        self._validate_service(service)
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                **persistent_context_options(self.profile_dir(service)),
            )
            page = context.new_page()
            page.goto(SERVICE_URLS[service], wait_until="domcontentloaded")
            input("Log in in the opened browser, then press Enter here to validate the profile...")
            status = self.validate_open_page(service, page)
            context.close()
        self.save_status(service, status)
        return status

    def check_status(self, service: str) -> ProfileStatus:
        self._validate_service(service)
        if not self.profile_dir(service).exists():
            self.save_status(service, ProfileStatus.NEEDS_SETUP)
            return ProfileStatus.NEEDS_SETUP
        from playwright.sync_api import sync_playwright

        try:
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(
                    **persistent_context_options(self.profile_dir(service)),
                )
                page = context.new_page()
                page.goto(SERVICE_URLS[service], wait_until="domcontentloaded", timeout=45000)
                status = self.validate_open_page(service, page)
                context.close()
        except Exception:
            status = ProfileStatus.BROKEN
        self.save_status(service, status)
        return status

    def validate_open_page(self, service: str, page) -> ProfileStatus:
        url = page.url.lower()
        body = page.locator("body").inner_text(timeout=10000).lower()
        if "sign in" in body or "log in" in body or "login" in url:
            return ProfileStatus.EXPIRED
        if service == "gemini":
            editable = page.locator("textarea, [contenteditable='true']").count()
            # Custom Gems can land on an intro screen before the chat composer is
            # mounted. If Google did not send us to a login screen, the profile
            # is usable and the flow can click through to the composer.
            if editable or "gemini.google.com" in url:
                return ProfileStatus.AUTHENTICATED
            return ProfileStatus.UNKNOWN
        if service == "freepik":
            generation_markers = ["generate", "prompt", "pikaso", "ai image"]
            return ProfileStatus.AUTHENTICATED if any(marker in body for marker in generation_markers) else ProfileStatus.UNKNOWN
        return ProfileStatus.UNKNOWN

    def _read_statuses(self) -> dict[str, str]:
        if not self.status_path.exists():
            return {}
        return json.loads(self.status_path.read_text(encoding="utf-8"))

    def _validate_service(self, service: str) -> None:
        if service not in SERVICE_URLS:
            raise ValueError(f"Unsupported browser profile service: {service}")
