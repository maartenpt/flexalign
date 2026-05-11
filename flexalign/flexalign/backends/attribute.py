"""Attribute backend."""

from __future__ import annotations

import re

from ..align.segment_adapter import segment_attr_for_align, segment_views_from_align_doc
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
        for view in segment_views_from_align_doc(src, level):
            key = segment_attr_for_align(view, attr)
            if not key:
                continue
            if normalize:
                key = verse_normalizer(key)
            src_index.setdefault(key, []).append(view)
        rows = []
        for view in segment_views_from_align_doc(tgt, level):
            key = segment_attr_for_align(view, attr)
            if not key:
                continue
            if normalize:
                key = verse_normalizer(key)
            matches = src_index.get(key, [])
            for source_view in matches:
                alignment_basis = f"attribute:{attr}"
                rows.append(
                    {
                        "id1": [source_view.anchor_id],
                        "id2": [view.anchor_id],
                        "text1": source_view.text,
                        "text2": view.text,
                        "score": 1.0,
                        "edit": "auto",
                        "alignment_basis": alignment_basis,
                        "tuid_at_write_1": source_view.tuid,
                        "tuid_at_write_2": view.tuid,
                    }
                )
        return rows


BACKEND_SPEC = BackendSpec(
    name="attribute",
    description="Align by configurable structural attribute",
    factory=AttributeBackend,
    supported_steps=AttributeBackend.supported_steps,
)

