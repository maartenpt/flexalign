"""Tuid parsing and minting."""

from __future__ import annotations

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


def mint_tuid(textid: str, level: str, index: int, parent_tuid: str | None = None) -> str:
    if level == "text":
        return textid
    prefix = {"chapter": "ch", "p": "p", "s": "s", "tok": "w"}.get(level, level)
    if parent_tuid:
        return f"{parent_tuid}:{prefix}{index}"
    return f"{textid}:{prefix}{index}"

