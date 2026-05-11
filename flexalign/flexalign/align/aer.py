"""Alignment error rate computation."""

from __future__ import annotations

import json
from pathlib import Path


def _normalize_ids(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _extract_links_histalign(payload: dict) -> set[tuple[str, str]]:
    links: set[tuple[str, str]] = set()
    for row in payload.get("sentences", []):
        for left in _normalize_ids(row.get("id1")):
            for right in _normalize_ids(row.get("id2")):
                links.add((left, right))
    return links


def _extract_links_pair(payload: dict) -> set[tuple[str, str]]:
    links: set[tuple[str, str]] = set()
    for group in payload.get("alignments", []):
        for row in group.get("pairs", []):
            for left in _normalize_ids(row.get("id1")):
                for right in _normalize_ids(row.get("id2")):
                    links.add((left, right))
    return links


def _extract_links(payload: dict) -> set[tuple[str, str]]:
    if "sentences" in payload:
        return _extract_links_histalign(payload)
    return _extract_links_pair(payload)


def compute_aer(gold: dict, auto: dict) -> float:
    auto_links = _extract_links(auto)
    sure = _extract_links(gold)
    possible = _extract_links(gold)
    if not auto_links and not sure:
        return 0.0
    return 1.0 - ((len(auto_links & sure) + len(auto_links & possible)) / (len(auto_links) + len(sure)))


def compute_aer_from_files(gold_path: str, auto_path: str) -> float:
    gold = json.loads(Path(gold_path).read_text(encoding="utf-8"))
    auto = json.loads(Path(auto_path).read_text(encoding="utf-8"))
    return compute_aer(gold, auto)

