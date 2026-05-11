"""Pairwise payload helpers."""

from __future__ import annotations


def empty_pairwise(version1: str, version2: str, level: str, parent_level: str | None, method: str, mode: str) -> dict:
    return {
        "version1": version1,
        "version2": version2,
        "level": level,
        "parent_level": parent_level,
        "pivot": "version1",
        "method": method,
        "mode": mode,
        "alignments": [],
    }

