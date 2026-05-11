"""CLI driver for ``flexalign convert``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..align.ir import AlignmentDocument
from .alignment_io_registry import alignment_registry, register_default_alignment_formats
from .tei_adapter import apply_alignment_document_to_tei


def _load_document(from_fmt: str, *, input_path: Path, kwargs: dict[str, Any]) -> AlignmentDocument:
    register_default_alignment_formats()
    entry = alignment_registry.get_input(from_fmt)
    if entry is None:
        raise ValueError(f"Unknown --from format: {from_fmt!r} (try: pair, reconcile, tmx, moses)")
    kind = entry.name.lower()
    if kind == "pair":
        return entry.loader(input_path, level=str(kwargs.get("level", "s")))
    if kind == "reconcile":
        v1 = kwargs.get("version1")
        v2 = kwargs.get("version2")
        if not v1 or not v2:
            raise ValueError("from reconcile: --version1 and --version2 are required (document paths in the reconcile file)")
        return entry.loader(input_path, version1=str(v1), version2=str(v2), level=str(kwargs.get("level", "s")))
    if kind == "tmx":
        return entry.loader(
            input_path,
            level=str(kwargs.get("level", "s")),
            version1=kwargs.get("version1"),
            version2=kwargs.get("version2"),
            lang_src=kwargs.get("lang_src"),
            lang_tgt=kwargs.get("lang_tgt"),
        )
    if kind == "moses":
        secondary = kwargs.get("moses_secondary")
        if not secondary:
            raise ValueError("from moses: --moses-secondary is required (parallel target file)")
        return entry.loader(
            input_path,
            moses_secondary=Path(secondary),
            level=str(kwargs.get("level", "s")),
            version1=kwargs.get("version1"),
            version2=kwargs.get("version2"),
            ids_path=Path(kwargs["ids_path"]) if kwargs.get("ids_path") else None,
        )
    raise ValueError(f"Unsupported input format: {kind!r}")


def _save_document(
    to_fmt: str,
    doc: AlignmentDocument,
    *,
    output_path: Path,
    kwargs: dict[str, Any],
) -> None:
    register_default_alignment_formats()
    if to_fmt.lower() in {"tei-writeback", "xml-writeback"}:
        pivot = kwargs.get("pivot_path")
        if not pivot:
            raise ValueError("to tei-writeback: --pivot is required (pivot TEI/XML path)")
        apply_alignment_document_to_tei(
            doc,
            pivot_path=Path(pivot),
            project_root=Path(kwargs["project_root"]).resolve() if kwargs.get("project_root") else None,
            out_dir=Path(kwargs["out_dir"]).resolve() if kwargs.get("out_dir") else None,
            ignore_tuid_drift=bool(kwargs.get("ignore_tuid_drift")),
            invalidate_below=bool(kwargs.get("invalidate_below")),
            mark_needs_review=bool(kwargs.get("mark_needs_review")),
        )
        return
    entry = alignment_registry.get_output(to_fmt)
    if entry is None:
        raise ValueError(
            f"Unknown --to format: {to_fmt!r} (try: pair, reconcile, tmx, moses, teitok, tei-writeback)"
        )
    kind = entry.name.lower()
    if kind == "pair":
        entry.saver(doc, output_path, level=kwargs.get("level"))
        return
    if kind == "reconcile":
        entry.saver(doc, output_path, level=kwargs.get("level"))
        return
    if kind == "tmx":
        ls_kw = kwargs.get("lang_src")
        lt_kw = kwargs.get("lang_tgt")
        lang_src = (str(ls_kw).strip() if ls_kw is not None else "") or doc.meta_extra.get("tmx_lang_src")
        lang_tgt = (str(lt_kw).strip() if lt_kw is not None else "") or doc.meta_extra.get("tmx_lang_tgt")
        lang_src = str(lang_src or "und")
        lang_tgt = str(lang_tgt or "und")
        entry.saver(
            doc,
            output_path,
            lang_src=str(lang_src),
            lang_tgt=str(lang_tgt),
            tuid_max_length=kwargs.get("tuid_max_length"),
            tuid_prefix=kwargs.get("tuid_prefix"),
        )
        return
    if kind == "teitok":
        ls_kw = kwargs.get("lang_src")
        lt_kw = kwargs.get("lang_tgt")
        lang_src = (str(ls_kw).strip() if ls_kw is not None else "") or doc.meta_extra.get("tmx_lang_src")
        lang_tgt = (str(lt_kw).strip() if lt_kw is not None else "") or doc.meta_extra.get("tmx_lang_tgt")
        lang_src = str(lang_src or "und")
        lang_tgt = str(lang_tgt or "und")
        entry.saver(
            doc,
            output_path,
            lang_src=str(lang_src),
            lang_tgt=str(lang_tgt),
            tuid_max_length=kwargs.get("tuid_max_length"),
            tuid_prefix=kwargs.get("tuid_prefix"),
        )
        return
    if kind == "moses":
        secondary = kwargs.get("moses_secondary")
        if not secondary:
            raise ValueError("to moses: --moses-secondary is required (target output file path)")
        entry.saver(
            doc,
            output_path,
            moses_tgt=Path(secondary),
            ids_path=Path(kwargs["moses_ids_out"]) if kwargs.get("moses_ids_out") else None,
        )
        return
    raise ValueError(f"Unsupported output format: {kind!r}")


def run_convert(
    *,
    from_fmt: str,
    to_fmt: str,
    input_path: Path,
    output_path: Path,
    moses_secondary: Path | None = None,
    version1: str | None = None,
    version2: str | None = None,
    lang_src: str | None = None,
    lang_tgt: str | None = None,
    level: str = "s",
    ids_path: str | None = None,
    pivot_path: str | None = None,
    project_root: str | None = None,
    out_dir: str | None = None,
    ignore_tuid_drift: bool = False,
    invalidate_below: bool = False,
    mark_needs_review: bool = False,
    moses_ids_out: str | None = None,
    tuid_max_length: int = 0,
    compact_tuids: bool = False,
    tuid_prefix: str | None = None,
) -> None:
    tuid_ml = tuid_max_length if tuid_max_length > 0 else None
    tp = (tuid_prefix or "").strip() or None
    kwargs: dict[str, Any] = {
        "level": level,
        "version1": version1,
        "version2": version2,
        "lang_src": lang_src,
        "lang_tgt": lang_tgt,
        "moses_secondary": str(moses_secondary) if moses_secondary else None,
        "ids_path": ids_path,
        "pivot_path": pivot_path,
        "project_root": project_root,
        "out_dir": out_dir,
        "ignore_tuid_drift": ignore_tuid_drift,
        "invalidate_below": invalidate_below,
        "mark_needs_review": mark_needs_review,
        "moses_ids_out": moses_ids_out,
        "tuid_max_length": tuid_ml,
        "compact_tuids": compact_tuids,
        "tuid_prefix": tp,
    }
    doc = _load_document(from_fmt, input_path=input_path, kwargs=kwargs)
    if compact_tuids:
        if tp:
            doc.compact_tuid_fields(prefix=tp)
        else:
            ml = tuid_ml if (tuid_ml is not None and tuid_ml > 0) else 56
            doc.compact_tuid_fields(max_length=ml)
    _save_document(to_fmt, doc, output_path=output_path, kwargs=kwargs)
