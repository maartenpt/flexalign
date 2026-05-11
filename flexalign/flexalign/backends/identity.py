"""Identity backend."""

from __future__ import annotations

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
        src_by_id = {unit.unit_id: unit for unit in src.iter_units(step.level if step else "s") if unit.unit_id}
        tgt_by_id = {unit.unit_id: unit for unit in tgt.iter_units(step.level if step else "s") if unit.unit_id}
        rows = []
        for unit_id in sorted(set(src_by_id).intersection(tgt_by_id)):
            rows.append(
                {
                    "id1": [unit_id],
                    "id2": [unit_id],
                    "text1": src_by_id[unit_id].text,
                    "text2": tgt_by_id[unit_id].text,
                    "score": 1.0,
                    "edit": "auto",
                    "tuid_at_write_1": src_by_id[unit_id].element.get("tuid"),
                    "tuid_at_write_2": tgt_by_id[unit_id].element.get("tuid"),
                }
            )
        return rows


BACKEND_SPEC = BackendSpec(
    name="identity",
    description="Align by shared xml:id",
    factory=IdentityBackend,
    supported_steps=IdentityBackend.supported_steps,
)

