"""TMX 1.4 import/export for alignment IR."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from lxml import etree

from ..align.ir import AlignmentDocument, AlignmentGroup, PairRow, ParentBlock
from ..align.tuid import compact_tuid, ordinal_export_tuid

XML_NS = "http://www.w3.org/XML/1998/namespace"
PROP_ID1 = "x-flexalign:id1"
PROP_ID2 = "x-flexalign:id2"


def _xml_lang(elem: etree._Element) -> str:
    return (elem.get(f"{{{XML_NS}}}lang") or elem.get("lang") or "").strip()


def _lang_matches(tuv_lang: str, requested: str) -> bool:
    """True if ``tuv``'s ``xml:lang`` matches ``requested`` (exact or same primary subtag)."""
    t = (tuv_lang or "").strip().lower().replace("_", "-")
    r = (requested or "").strip().lower().replace("_", "-")
    if not t or not r:
        return False
    if t == r:
        return True
    return t.split("-", 1)[0] == r.split("-", 1)[0]


def _resolve_src_tgt_tuvs(
    tu: etree._Element,
    tuvs: list[etree._Element],
    *,
    lang_src: str | None,
    lang_tgt: str | None,
) -> tuple[etree._Element, etree._Element]:
    """
    Choose pivot (source) and target ``tuv`` for this ``tu``.

    If ``lang_src`` and ``lang_tgt`` are both set, match by relaxed BCP47 rules.
    Otherwise, if the ``<tu>`` has ``srclang``, use the ``tuv`` that matches ``srclang`` as
    source and another ``tuv`` as target (so ``tuv`` order in the file does not swap sides).
    Otherwise fall back to document order: first ``tuv`` = source, second = target.
    """
    if lang_src and lang_tgt:
        return _pick_src_tgt_tuvs(tuvs, lang_src=lang_src, lang_tgt=lang_tgt)
    srclang = (tu.get("srclang") or "").strip()
    if srclang and len(tuvs) >= 2:
        i_src = next((i for i, t in enumerate(tuvs) if _lang_matches(_xml_lang(t), srclang)), None)
        if i_src is not None:
            i_tgt = next((i for i in range(len(tuvs)) if i != i_src), None)
            if i_tgt is not None:
                return tuvs[i_src], tuvs[i_tgt]
    return tuvs[0], tuvs[1]


def _pick_src_tgt_tuvs(
    tuvs: list[etree._Element],
    *,
    lang_src: str | None,
    lang_tgt: str | None,
) -> tuple[etree._Element, etree._Element]:
    """Pick source/target ``tuv`` for this ``tu``, using relaxed BCP47-style language matching."""
    if not lang_src or not lang_tgt or len(tuvs) < 2:
        return tuvs[0], tuvs[1]
    src_idx = next((i for i, t in enumerate(tuvs) if _lang_matches(_xml_lang(t), lang_src)), None)
    tgt_idx = next((i for i, t in enumerate(tuvs) if _lang_matches(_xml_lang(t), lang_tgt)), None)
    if src_idx is None:
        src_idx = 0
    if tgt_idx is None or tgt_idx == src_idx:
        tgt_idx = next(
            (
                i
                for i, t in enumerate(tuvs)
                if i != src_idx and _lang_matches(_xml_lang(t), lang_tgt)
            ),
            None,
        )
    if tgt_idx is None or tgt_idx == src_idx:
        tgt_idx = next((i for i in range(len(tuvs)) if i != src_idx), 1 if len(tuvs) > 1 else 0)
    return tuvs[src_idx], tuvs[tgt_idx]


def _seg_text(tuv: etree._Element) -> str:
    for seg in tuv.xpath("./*[local-name()='seg']"):
        return "".join(seg.itertext()).strip()
    return "".join(tuv.itertext()).strip()


def _prop_text(tu: etree._Element, prop_type: str) -> str | None:
    for prop in tu.xpath("./*[local-name()='prop']"):
        if (prop.get("type") or "").strip() == prop_type:
            return (prop.text or "").strip() or None
    return None


def _split_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in raw.split("|") if p.strip()]


def load_alignment_from_tmx(
    path: str | Path,
    *,
    version1: str | None = None,
    version2: str | None = None,
    lang_src: str | None = None,
    lang_tgt: str | None = None,
    level: str = "s",
) -> AlignmentDocument:
    """
    Parse TMX into a pair-shaped AlignmentDocument.

    Uses ``<prop type="x-flexalign:id1">`` / ``id2`` when present (pipe-separated ids).
    Otherwise mints synthetic anchors ``tmx:{n}:a`` / ``tmx:{n}:b``.

    When ``lang_src`` / ``lang_tgt`` are set, ``<tuv xml:lang>`` is matched with the same primary
    language subtag (e.g. ``en`` matches ``en-US``) so ``tuv`` order in the file matters less.

    When they are omitted, ``<tu srclang="…">`` (TMX 1.4) picks the source ``tuv`` if present;
    otherwise the first two ``tuv`` elements are used in order.

    The chosen ``xml:lang`` values (first row where each side is non-empty) are stored in
    ``meta_extra`` as ``tmx_lang_src`` and ``tmx_lang_tgt`` for exporters (e.g. teitok) when
    ``--lang-src`` / ``--lang-tgt`` are not passed on ``convert``.
    """
    path = Path(path)
    tree = etree.parse(str(path), etree.XMLParser(remove_blank_text=False, recover=True))
    root = tree.getroot()
    tus = root.xpath(".//*[local-name()='tu']")
    v1 = version1 or f"{path.name}:src"
    v2 = version2 or f"{path.name}:tgt"
    rows: list[PairRow] = []
    detected: tuple[str, str] | None = None
    witness_lang_src: str | None = None
    witness_lang_tgt: str | None = None
    for index, tu in enumerate(tus):
        tuvs = tu.xpath("./*[local-name()='tuv']")
        if len(tuvs) < 2:
            continue
        langs = [_xml_lang(t) for t in tuvs[:2]]
        if detected is None and langs[0] and langs[1]:
            detected = (langs[0], langs[1])
        src_tuv, tgt_tuv = _resolve_src_tgt_tuvs(tu, tuvs, lang_src=lang_src, lang_tgt=lang_tgt)
        text1 = _seg_text(src_tuv)
        text2 = _seg_text(tgt_tuv)
        la, lb = _xml_lang(src_tuv), _xml_lang(tgt_tuv)
        if witness_lang_src is None and la:
            witness_lang_src = la
        if witness_lang_tgt is None and lb:
            witness_lang_tgt = lb
        id1 = _split_ids(_prop_text(tu, PROP_ID1))
        id2 = _split_ids(_prop_text(tu, PROP_ID2))
        if not id1:
            id1 = [f"tmx:{index + 1}:a"]
        if not id2:
            id2 = [f"tmx:{index + 1}:b"]
        tuid_attr = (tu.get("tuid") or "").strip() or None
        rows.append(
            PairRow(
                id1=id1,
                id2=id2,
                text1=text1,
                text2=text2,
                score=1.0,
                edit="auto",
                tuid_at_write_1=tuid_attr,
                tuid_at_write_2=tuid_attr,
            )
        )
    method_detail = "tmx-import"
    if detected:
        method_detail = f"tmx-import:{detected[0]}->{detected[1]}"
    meta_extra: dict[str, Any] = {"source_tmx": str(path).replace("\\", "/")}
    if witness_lang_src:
        meta_extra["tmx_lang_src"] = witness_lang_src
    if witness_lang_tgt:
        meta_extra["tmx_lang_tgt"] = witness_lang_tgt
    return AlignmentDocument(
        version1=v1,
        version2=v2,
        level=level,
        parent_level=None,
        pivot="version1",
        method="tmx",
        mode="direct",
        alignments=[AlignmentGroup(parent=ParentBlock(id1=[], id2=[]), pairs=rows)],
        method_detail=method_detail,
        notes=[],
        meta_extra=meta_extra,
    )


def write_alignment_to_tmx(
    doc: AlignmentDocument,
    path: str | Path,
    *,
    lang_src: str,
    lang_tgt: str,
    tuid_max_length: int | None = None,
    tuid_prefix: str | None = None,
) -> None:
    """Write alignment rows to a minimal TMX 1.4 document (UTF-8)."""
    path = Path(path)
    out: list[str] = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(f'<tmx version="1.4" xmlns:xml="{XML_NS}">')
    out.append("  <header>")
    out.append(f'    <prop type="x-flexalign:version1">{escape(doc.version1)}</prop>')
    out.append(f'    <prop type="x-flexalign:version2">{escape(doc.version2)}</prop>')
    out.append(f'    <prop type="x-flexalign:level">{escape(doc.level)}</prop>')
    out.append("  </header>")
    out.append("  <body>")
    index = 0
    pfx = (tuid_prefix or "").strip()
    doc_level = (doc.level or "s").strip().lower()
    for group in doc.alignments:
        for row in group.pairs:
            index += 1
            if pfx:
                tuid = ordinal_export_tuid(pfx, index, level=doc_level)
            else:
                tuid = (row.tuid_at_write_1 or row.tuid_at_write_2 or "").strip()
                if tuid and tuid_max_length is not None and tuid_max_length > 0:
                    tuid = compact_tuid(tuid, max_length=tuid_max_length) or tuid
            tu_open = "    <tu"
            if tuid:
                safe_tuid = tuid.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
                tu_open += f' tuid="{safe_tuid}"'
            tu_open += ">"
            out.append(tu_open)
            if row.id1:
                out.append(f'      <prop type="{PROP_ID1}">{escape("|".join(row.id1))}</prop>')
            if row.id2:
                out.append(f'      <prop type="{PROP_ID2}">{escape("|".join(row.id2))}</prop>')
            out.append(f'    <tuv xml:lang="{escape(lang_src)}">')
            out.append(f"      <seg>{escape(row.text1)}</seg>")
            out.append("    </tuv>")
            out.append(f'    <tuv xml:lang="{escape(lang_tgt)}">')
            out.append(f"      <seg>{escape(row.text2)}</seg>")
            out.append("    </tuv>")
            out.append("    </tu>")
    out.append("  </body>")
    out.append("</tmx>")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def export_tmx(path: str | Path, payload: dict, *, lang_src: str = "en", lang_tgt: str = "und") -> None:
    """Backward-compatible entry: pair payload dict to TMX."""
    write_alignment_to_tmx(AlignmentDocument.from_pair_payload(payload), path, lang_src=lang_src, lang_tgt=lang_tgt)
