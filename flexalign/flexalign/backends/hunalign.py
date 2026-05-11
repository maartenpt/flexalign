"""Hunalign backend wrapper (scaffold)."""

from __future__ import annotations

from ..backend_spec import BackendSpec, StepSpec


class HunalignBackend:
    name = "hunalign"
    supported_steps = (
        StepSpec("text", "p", "direct"),
        StepSpec("text", "s", "direct"),
        StepSpec("chapter", "p", "direct"),
        StepSpec("chapter", "s", "direct"),
        StepSpec("p", "s", "direct"),
    )

    def align(self, src, tgt, *, step=None, parent_pairs=None, options=None):
        # Scaffold: fallback to attribute-style structural alignment by xml:id.
        from .identity import IdentityBackend

        return IdentityBackend().align(src, tgt, step=step, parent_pairs=parent_pairs, options=options)


BACKEND_SPEC = BackendSpec(
    name="hunalign",
    description="Hunalign CLI backend wrapper",
    factory=HunalignBackend,
    supported_steps=HunalignBackend.supported_steps,
    install_instructions='Install extras with: pip install "flexalign[hunalign]"',
)

