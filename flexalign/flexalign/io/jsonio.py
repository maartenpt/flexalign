"""JSON helpers."""

from __future__ import annotations

import json
from pathlib import Path


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(payload: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def migrate_histalign_payload(payload: dict) -> dict:
    version1 = payload.get("version1")
    version2 = payload.get("version2")
    alignments = []
    for row in payload.get("sentences", []):
        id1 = [item.strip() for item in str(row.get("id1", "")).split(",") if item.strip()]
        id2 = [item.strip() for item in str(row.get("id2", "")).split(",") if item.strip()]
        alignments.append(
            {
                "parent": {"id1": [], "id2": [], "tuid_at_write_1": None, "tuid_at_write_2": None},
                "pairs": [
                    {
                        "id1": id1,
                        "id2": id2,
                        "text1": row.get("text1", ""),
                        "text2": row.get("text2", ""),
                        "score": 1.0,
                        "edit": "manual",
                        "tuid_at_write_1": None,
                        "tuid_at_write_2": None,
                    }
                ],
            }
        )
    return {
        "version1": version1,
        "version2": version2,
        "level": "s",
        "parent_level": "p",
        "pivot": "version1",
        "method": payload.get("method", "histalign"),
        "mode": "direct",
        "alignments": alignments,
    }


def migrate_histalign_file(source: Path, target: Path) -> None:
    payload = json.loads(source.read_text(encoding="utf-8"))
    save_json(migrate_histalign_payload(payload), target)

