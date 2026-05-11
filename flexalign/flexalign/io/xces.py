"""XCES export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_xces(path: str | Path, payload: dict) -> None:
    Path(path).write_text("<xces></xces>\n", encoding="utf-8")

