"""Rollup projection helpers."""

from __future__ import annotations

from typing import Iterable


def project_rollup(child_pairs: Iterable[dict], threshold: float) -> list[dict]:
    projected: list[dict] = []
    for pair in child_pairs:
        if float(pair.get("score", 0.0)) >= threshold:
            projected.append(pair)
    return projected


def chunk_sentence_windows(sentences: list[str], *, subtoken_cap: int = 480, overlap_sentences: int = 1) -> list[list[str]]:
    if not sentences:
        return []
    windows: list[list[str]] = []
    current: list[str] = []
    current_size = 0
    for sentence in sentences:
        approx = max(1, len(sentence.split()))
        if current and current_size + approx > subtoken_cap:
            windows.append(current)
            current = current[-overlap_sentences:] if overlap_sentences > 0 else []
            current_size = sum(len(item.split()) for item in current)
        current.append(sentence)
        current_size += approx
    if current:
        windows.append(current)
    return windows

