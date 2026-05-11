"""Cascade orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..backend_registry import get_backend
from ..io.jsonio import save_json
from ..io.teitok import load_teitok
from .projection import segment_from_pivot


def _parse_backend_map(spec: str) -> dict[str, tuple[str, str]]:
    mapping: dict[str, tuple[str, str]] = {}
    if not spec:
        return mapping
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        backend, level_mode = chunk.split(":", 1)
        if "/" in level_mode:
            level, mode = level_mode.split("/", 1)
        else:
            level, mode = level_mode, "direct"
        mapping[level] = (backend, mode)
    return mapping


def align_single(*, backend: str, level: str, pivot_path: str, target_path: str, attr: str = "xml:id") -> dict:
    from ..backends.attribute import AttributeBackend
    from ..backends.identity import IdentityBackend

    step = SimpleNamespace(level=level)
    src = load_teitok(pivot_path)
    tgt = load_teitok(target_path)
    if backend == "identity":
        rows = IdentityBackend().align(src, tgt, step=step, parent_pairs=[], options={})
    elif backend == "attribute":
        rows = AttributeBackend().align(src, tgt, step=step, parent_pairs=[], options={"attr": attr})
    else:
        spec = get_backend(backend)
        if spec is None:
            raise ValueError(f"Unknown backend: {backend}")
        rows = spec.factory().align(src, tgt, step=step, parent_pairs=[], options={})
    rows = sorted(rows, key=lambda row: (tuple(row.get("id1", [])), tuple(row.get("id2", []))))
    method_detail = backend
    if backend == "attribute":
        method_detail = f"attribute:{attr}"
    notes: list[str] = []
    if backend == "attribute" and level == "tok" and attr == "tuid":
        notes.append(
            "Token mapping is based on projected/shared token tuids (bootstrap alignment), not lexical token translation."
        )
    return {
        "version1": pivot_path,
        "version2": target_path,
        "level": level,
        "parent_level": None,
        "pivot": "version1",
        "method": backend,
        "method_detail": method_detail,
        "mode": "direct",
        "notes": notes,
        "alignments": [
            {
                "parent": {
                    "id1": [],
                    "id2": [],
                    "tuid_at_write_1": None,
                    "tuid_at_write_2": None,
                },
                "pairs": rows,
            }
        ],
    }


def run_cascade(
    *,
    pivot_path: str,
    target_path: str,
    steps: list[str],
    out_dir: Path,
    backends: str = "",
    segment_level: str | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    mapping = _parse_backend_map(backends)

    def _attr_for_level(level_name: str) -> str:
        if level_name in {"ab", "s", "tok"}:
            return "tuid"
        return "n"

    for index, level in enumerate(steps):
        parent_level = steps[index - 1] if index > 0 else None
        backend_name, mode = mapping.get(level, ("identity" if level in {"text", "chapter"} else "attribute", "direct"))
        # If lower-level segmentation is missing, project it before alignment.
        if level in {"s", "tok"}:
            src_doc = load_teitok(pivot_path)
            tgt_doc = load_teitok(target_path)
            if not src_doc.iter_units(level):
                segment_from_pivot(level, target_path, pivot_path, None)
                src_doc = load_teitok(pivot_path)
            if not tgt_doc.iter_units(level):
                segment_from_pivot(level, pivot_path, target_path, None)
        payload = align_single(
            backend=backend_name,
            level=level,
            pivot_path=pivot_path,
            target_path=target_path,
            attr=_attr_for_level(level),
        )
        payload["parent_level"] = parent_level
        payload["mode"] = mode
        save_json(payload, out_dir / f"pair_{Path(pivot_path).stem}_{Path(target_path).stem}_{level}.json")
        if segment_level == level:
            segment_from_pivot(level, pivot_path, target_path, None)


run_cascade.align_single = align_single

