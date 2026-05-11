"""Sanitize strings for use as XML / NCName fragments."""

from __future__ import annotations

import re

_NCNAME_INVALID = re.compile(r"[^A-Za-z0-9_.\-]")


def safe_xml_id_fragment(value: str) -> str:
    """Turn an arbitrary string into a conservative NCName-friendly fragment."""
    s = _NCNAME_INVALID.sub("_", (value or "").strip())
    if not s:
        return "x"
    if s[0].isdigit() or s[0] in {".", "-"}:
        s = "x" + s
    return s[:200]
