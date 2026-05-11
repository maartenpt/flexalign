"""Tuid parsing and minting."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict


def parse_tuid(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = re.sub(r"\s+", "|", value.strip())
    return [part for part in normalized.split("|") if part]


def join_tuids(values: list[str]) -> str:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return "|".join(seen)


def derive_counters(existing_tuids: list[str]) -> dict[str, int]:
    counters = defaultdict(int)
    for tuid in existing_tuids:
        for part in parse_tuid(tuid):
            for token in re.findall(r"(\d+)", part):
                counters["global"] = max(counters["global"], int(token))
    return {"global": counters["global"] + 1}


def _tuid_digest_token(s: str) -> str:
    """Stable short token (``t`` + 20 hex) for a single tuid fragment."""
    h = hashlib.blake2b(s.encode("utf-8"), digest_size=10).hexdigest()
    return f"t{h}"


def ordinal_export_tuid(prefix: str, row_index: int, *, level: str = "s") -> str:
    """
    Human-readable tuid for export: ``{prefix}-s1``, ``-s2``, … for sentence-level rows,
    or ``{prefix}-w1``, … when ``level`` is ``tok`` (one index per alignment row).
    ``prefix`` is sanitized for safe use in XML id-like contexts.
    """
    from ..io.xml_id import safe_xml_id_fragment

    base = safe_xml_id_fragment((prefix or "").strip())
    if not base:
        base = "tu"
    lv = (level or "s").lower()
    if lv == "tok":
        return f"{base}-w{row_index}"
    return f"{base}-s{row_index}"


def compact_tuid(value: str | None, *, max_length: int = 56) -> str | None:
    """
    Shorten a tuid (or pipe-joined bundle) when fragments exceed ``max_length``.

    Long fragments are replaced with ``t`` + 20 hex chars (blake2b-10), which is
    stable, collision-resistant, and valid in XML ``NCName`` contexts. Short
    fragments and values under the limit are unchanged.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if max_length <= 0:
        return s
    parts = parse_tuid(s)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) <= max_length:
            out.append(p)
        else:
            out.append(_tuid_digest_token(p))
    return join_tuids(out)


def mint_tuid(textid: str, level: str, index: int, parent_tuid: str | None = None) -> str:
    if level == "text":
        return textid
    prefix = {"chapter": "ch", "p": "p", "s": "s", "tok": "w"}.get(level, level)
    if parent_tuid:
        return f"{parent_tuid}:{prefix}{index}"
    return f"{textid}:{prefix}{index}"

