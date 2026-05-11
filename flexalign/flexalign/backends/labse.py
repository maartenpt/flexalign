"""LaBSE backend scaffold."""

from __future__ import annotations

from ..backend_spec import BackendSpec, StepSpec


class LabseBackend:
    name = "labse"
    supported_steps = (
        StepSpec("text", "p", "direct"),
        StepSpec("text", "s", "direct"),
        StepSpec("chapter", "p", "direct"),
        StepSpec("chapter", "s", "direct"),
        StepSpec("p", "s", "direct"),
    )

    def align(self, src, tgt, *, step=None, parent_pairs=None, options=None):
        from .identity import IdentityBackend

        return IdentityBackend().align(src, tgt, step=step, parent_pairs=parent_pairs, options=options)


BACKEND_SPEC = BackendSpec(
    name="labse",
    description="LaBSE + PolyFuzz backend",
    factory=LabseBackend,
    supported_steps=LabseBackend.supported_steps,
    install_instructions='Install extras with: pip install "flexalign[labse]"',
)

