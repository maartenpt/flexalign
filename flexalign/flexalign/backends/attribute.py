"""Attribute backend."""

from __future__ import annotations

import re

from ..backend_spec import BackendSpec, StepSpec


def verse_normalizer(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"[,:]", ".", cleaned)
    parts = [part.lstrip("0") or "0" for part in cleaned.split(".")]
    return ".".join(parts)


class AttributeBackend:
    name = "attribute"
    supported_steps = (
        StepSpec("text", "chapter", "direct"),
        StepSpec("text", "p", "direct"),
        StepSpec("text", "s", "direct"),
        StepSpec("chapter", "p", "direct"),
        StepSpec("chapter", "s", "direct"),
    )

    def align(self, src, tgt, *, step=None, parent_pairs=None, options=None):
        options = options or {}
        level = step.level if step else "s"
        attr = options.get("attr", "n")
        normalize = options.get("normalize", False)
        src_index = {}
        for unit in src.iter_units(level):
            key = unit.element.get(attr) or unit.element.get("{http://www.w3.org/XML/1998/namespace}id") or unit.unit_id
            if not key:
                continue
            if normalize:
                key = verse_normalizer(key)
            src_index.setdefault(key, []).append(unit)
        rows = []
        for unit in tgt.iter_units(level):
            key = unit.element.get(attr) or unit.element.get("{http://www.w3.org/XML/1998/namespace}id") or unit.unit_id
            if not key:
                continue
            if normalize:
                key = verse_normalizer(key)
            matches = src_index.get(key, [])
            for source_unit in matches:
                alignment_basis = f"attribute:{attr}"
                rows.append(
                    {
                        "id1": [source_unit.unit_id],
                        "id2": [unit.unit_id],
                        "text1": source_unit.text,
                        "text2": unit.text,
                        "score": 1.0,
                        "edit": "auto",
                        "alignment_basis": alignment_basis,
                        "tuid_at_write_1": source_unit.element.get("tuid"),
                        "tuid_at_write_2": unit.element.get("tuid"),
                    }
                )
        return rows


BACKEND_SPEC = BackendSpec(
    name="attribute",
    description="Align by configurable structural attribute",
    factory=AttributeBackend,
    supported_steps=AttributeBackend.supported_steps,
)

