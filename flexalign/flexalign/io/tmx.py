"""TMX export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_tmx(path: str | Path, payload: dict) -> None:
    Path(path).write_text("<tmx></tmx>\n", encoding="utf-8")

