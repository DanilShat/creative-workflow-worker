"""Tests for GeminiPromptFlow wrapper stripping and URL selection."""

from creative_workflow.worker.browser.flows.gemini_prompt import (
    PHOTO_GEM_URL,
    VIDEO_GEM_URL,
    _strip_gemini_wrapper,
)


# ---------------------------------------------------------------------------
# _strip_gemini_wrapper
# ---------------------------------------------------------------------------

def test_strip_wrapper_removes_claude_preamble_before_shot_marker() -> None:
    wrapped = (
        "Perfect! Gemini has completed the prompt generation for your product. "
        "Here is the result:\n\n"
        "SHOT: Close-up on a glass bottle against a white studio background.\n"
        "STYLE: Minimalist, high contrast.\n"
    )
    result = _strip_gemini_wrapper(wrapped)
    assert result.startswith("SHOT:")
    assert "Perfect!" not in result


def test_strip_wrapper_leaves_already_clean_prompt_unchanged() -> None:
    clean = "SHOT: Overhead macro of a coffee cup.\nSTYLE: Warm tones."
    assert _strip_gemini_wrapper(clean) == clean


def test_strip_wrapper_returns_original_when_no_marker_found() -> None:
    text = "A rich, cinematic product hero image."
    assert _strip_gemini_wrapper(text) == text


def test_strip_wrapper_finds_earliest_marker_among_multiple() -> None:
    text = "Some preamble text. SCENE: outdoor plaza. SHOT: close-up product."
    result = _strip_gemini_wrapper(text)
    assert result.startswith("SCENE:")


def test_strip_wrapper_handles_empty_string() -> None:
    assert _strip_gemini_wrapper("") == ""


# ---------------------------------------------------------------------------
# URL selection
# ---------------------------------------------------------------------------

def test_photo_gem_url_matches_handoff_spec() -> None:
    assert PHOTO_GEM_URL == "https://gemini.google.com/gem/4dd4618f8ae1"


def test_video_gem_url_is_unchanged() -> None:
    assert VIDEO_GEM_URL == "https://gemini.google.com/gem/21d5be0eae0a"
