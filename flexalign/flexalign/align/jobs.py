"""Simple job files management."""

from __future__ import annotations

import json
from pathlib import Path


def write_job_spec(job_dir: Path, job_id: str, payload: dict) -> Path:
    job_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / f"{job_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

