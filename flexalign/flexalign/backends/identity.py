"""Identity backend."""

from __future__ import annotations

from ..align.segment_adapter import segment_views_from_align_doc
from ..backend_spec import BackendSpec, StepSpec


class IdentityBackend:
    name = "identity"
    supported_steps = (
        StepSpec("text", "chapter", "direct"),
        StepSpec("text", "p", "direct"),
        StepSpec("text", "s", "direct"),
        StepSpec("chapter", "p", "direct"),
    )

    def align(self, src, tgt, *, step=None, parent_pairs=None, options=None):
        level = step.level if step else "s"
        src_views = segment_views_from_align_doc(src, level)
        tgt_views = segment_views_from_align_doc(tgt, level)
        src_by_id = {v.anchor_id: v for v in src_views if v.anchor_id}
        tgt_by_id = {v.anchor_id: v for v in tgt_views if v.anchor_id}
        rows = []
        for unit_id in sorted(set(src_by_id).intersection(tgt_by_id)):
            sv = src_by_id[unit_id]
            tv = tgt_by_id[unit_id]
            rows.append(
                {
                    "id1": [unit_id],
                    "id2": [unit_id],
                    "text1": sv.text,
                    "text2": tv.text,
                    "score": 1.0,
                    "edit": "auto",
                    "tuid_at_write_1": sv.tuid,
                    "tuid_at_write_2": tv.tuid,
                }
            )
        return rows


BACKEND_SPEC = BackendSpec(
    name="identity",
    description="Align by shared xml:id",
    factory=IdentityBackend,
    supported_steps=IdentityBackend.supported_steps,
)

