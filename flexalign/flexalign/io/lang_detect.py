"""Optional language detection for plain-text witnesses."""

from __future__ import annotations


def detect_language(text: str) -> str | None:
    """
    Return a BCP47-ish code or None.

    Uses ``langdetect`` when installed; otherwise returns None.
    """
    sample = (text or "").strip()
    if len(sample) < 20:
        return None
    try:
        from langdetect import detect

        return str(detect(sample[:5000]))
    except Exception:
        return None
