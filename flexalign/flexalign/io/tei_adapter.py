"""TEI / TEITOK adapters: segment views and TUID writeback from alignment IR."""

from __future__ import annotations

from pathlib import Path

from ..align.apply import apply_pair_payload
from ..align.ir import AlignmentDocument
from ..align.segment_adapter import segment_views_from_align_doc
from .teitok import load_teitok


def read_segment_views_from_tei(path: str | Path, level: str):
    """Load TEI/XML and return segment views at the given structural level."""
    return segment_views_from_align_doc(load_teitok(path), level)


def apply_alignment_document_to_tei(
    doc: AlignmentDocument,
    *,
    pivot_path: Path,
    project_root: Path | None = None,
    out_dir: Path | None = None,
    ignore_tuid_drift: bool = False,
    invalidate_below: bool = False,
    mark_needs_review: bool = False,
) -> None:
    """Apply pair-shaped IR to TEI targets (same semantics as ``apply`` on pair JSON)."""
    apply_pair_payload(
        doc.to_pair_payload(),
        pivot_path=pivot_path,
        project_root=project_root,
        out_dir=out_dir,
        ignore_tuid_drift=ignore_tuid_drift,
        invalidate_below=invalidate_below,
        mark_needs_review=mark_needs_review,
    )
