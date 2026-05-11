"""Plain-text directory → minimal TEI → alignment → optional export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from ..align.cascade import align_single
from ..align.ir import AlignmentDocument
from .builtin_plain_segment import plain_to_sentences_and_tokens
from .flexipipe_plain_bridge import flexipipe_available, plain_to_sentences_and_tokens_flexipipe
from .lang_detect import detect_language
from .minimal_tei_writer import write_minimal_tei
from .moses import write_alignment_to_moses
from .tmx import write_alignment_to_tmx
from .xml_id import safe_xml_id_fragment

SegmenterName = Literal["builtin", "flexipipe"]


def _segment_plain(text: str, *, level: str, segmenter: SegmenterName) -> tuple[list[str], list[list[str]] | None]:
    if segmenter == "flexipipe":
        if not flexipipe_available():
            raise RuntimeError(
                "segmenter=flexipipe requires the flexipipe package. "
                "Install flexipipe in this environment (e.g. pip install -e ../flexipipe)."
            )
        return plain_to_sentences_and_tokens_flexipipe(text, level=level)
    return plain_to_sentences_and_tokens(text, level=level)


def prepare_txt_to_tei(
    source_txt: Path,
    dest_tei: Path,
    *,
    level: str,
    segmenter: SegmenterName,
    lang: str | None,
    detect_lang: bool,
    title: str | None = None,
) -> dict[str, Any]:
    """Read one UTF-8 text file and write minimal TEI. Returns witness metadata dict."""
    text = source_txt.read_text(encoding="utf-8")
    resolved_lang = lang
    if detect_lang and not resolved_lang:
        resolved_lang = detect_language(text)
    sents, toks = _segment_plain(text, level=level, segmenter=segmenter)
    sents = [s for s in sents if s.strip()]
    if level == "tok" and toks is not None:
        paired = [(s, t) for s, t in zip(sents, toks) if t]
        if not paired:
            raise ValueError(f"No tokenized sentences produced for {source_txt}")
        sents = [p[0] for p in paired]
        toks = [p[1] for p in paired]
    elif level != "tok":
        toks = None
    write_minimal_tei(
        dest_tei,
        sentences=sents,
        token_rows=toks,
        title=title or source_txt.stem,
        lang=resolved_lang,
    )
    return {
        "source": str(source_txt).replace("\\", "/"),
        "tei": str(dest_tei).replace("\\", "/"),
        "lang": resolved_lang,
        "title": source_txt.stem,
    }


def prepare_directory(
    input_dir: Path,
    out_dir: Path,
    *,
    glob_pattern: str = "*.txt",
    recursive: bool = False,
    level: str,
    segmenter: SegmenterName,
    default_lang: str | None = None,
    detect_lang: bool = False,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    """
    Convert each matching ``.txt`` file under ``input_dir`` to minimal TEI in ``out_dir``.

    Output filenames: ``{safe_stem}.tei.xml``.
    """
    input_dir = input_dir.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if recursive:
        paths = sorted(input_dir.rglob(glob_pattern))
    else:
        paths = sorted(input_dir.glob(glob_pattern))
    paths = [p for p in paths if p.is_file()]
    witnesses: list[dict[str, Any]] = []
    for p in paths:
        stem = safe_xml_id_fragment(p.stem)
        dest = out_dir / f"{stem}.tei.xml"
        meta = prepare_txt_to_tei(
            p,
            dest,
            level=level,
            segmenter=segmenter,
            lang=default_lang,
            detect_lang=detect_lang,
            title=p.stem,
        )
        witnesses.append(meta)
    payload = {
        "input_dir": str(input_dir).replace("\\", "/"),
        "out_dir": str(out_dir).replace("\\", "/"),
        "glob": glob_pattern,
        "recursive": recursive,
        "level": level,
        "segmenter": segmenter,
        "witnesses": witnesses,
    }
    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _resolve_te_path(path: Path, work_dir: Path, *, level: str, segmenter: SegmenterName, lang: str | None, detect: bool) -> Path:
    path = path.resolve()
    if path.suffix.lower() in {".xml", ".tei"} or path.name.endswith(".tei.xml"):
        return path
    if path.suffix.lower() != ".txt":
        raise ValueError(f"Expected .txt or TEI/XML, got: {path}")
    work_dir.mkdir(parents=True, exist_ok=True)
    stem = safe_xml_id_fragment(path.stem)
    dest = work_dir / f"{stem}.tei.xml"
    prepare_txt_to_tei(path, dest, level=level, segmenter=segmenter, lang=lang, detect_lang=detect)
    return dest


def align_plain_or_tei_pair(
    pivot: Path,
    target: Path,
    output_pair: Path,
    *,
    work_dir: Path,
    backend: str,
    level: str,
    attr: str = "xml:id",
    segmenter: SegmenterName = "builtin",
    lang: str | None = None,
    detect_lang: bool = False,
    export_tmx: Path | None = None,
    export_tmx_lang_src: str | None = None,
    export_tmx_lang_tgt: str | None = None,
    export_moses_src: Path | None = None,
    export_moses_tgt: Path | None = None,
    export_moses_ids: Path | None = None,
) -> dict[str, Any]:
    """
    Resolve pivot/target (``.txt`` → minimal TEI in ``work_dir``), run ``align_single``, save pair JSON.

    Optional TMX / Moses exports.
    """
    work_dir = work_dir.resolve()
    pivot_tei = _resolve_te_path(pivot, work_dir, level=level, segmenter=segmenter, lang=lang, detect=detect_lang)
    target_tei = _resolve_te_path(target, work_dir, level=level, segmenter=segmenter, lang=lang, detect=detect_lang)
    payload = align_single(
        backend=backend,
        level=level,
        pivot_path=str(pivot_tei),
        target_path=str(target_tei),
        attr=attr,
    )
    output_pair.parent.mkdir(parents=True, exist_ok=True)
    output_pair.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = AlignmentDocument.from_pair_payload(payload)
    if export_tmx:
        ls = export_tmx_lang_src or "en"
        lt = export_tmx_lang_tgt or "und"
        write_alignment_to_tmx(doc, export_tmx, lang_src=ls, lang_tgt=lt)
    if export_moses_src or export_moses_tgt or export_moses_ids:
        if not (export_moses_src and export_moses_tgt):
            raise ValueError("Moses export requires both export_moses_src and export_moses_tgt paths")
        write_alignment_to_moses(doc, export_moses_src, export_moses_tgt, ids_path=export_moses_ids)
    return {
        "pivot_tei": str(pivot_tei).replace("\\", "/"),
        "target_tei": str(target_tei).replace("\\", "/"),
        "pair": str(output_pair).replace("\\", "/"),
    }
