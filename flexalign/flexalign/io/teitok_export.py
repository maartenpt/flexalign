"""Write a new TEI / TEITOK-friendly XML document from alignment IR (no existing pivot file)."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from ..align.ir import AlignmentDocument
from ..align.tuid import compact_tuid, ordinal_export_tuid
from .xml_id import safe_xml_id_fragment

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _primary_anchor(ids: list[str], fallback: str) -> str:
    if ids:
        return safe_xml_id_fragment(str(ids[0]))
    return safe_xml_id_fragment(fallback)


def _tuid_for_row(tuid1: str | None, tuid2: str | None, *, tuid_max_length: int | None) -> str | None:
    t = (tuid1 or tuid2 or "").strip()
    if not t:
        return None
    if tuid_max_length is not None and tuid_max_length > 0:
        return compact_tuid(t, max_length=tuid_max_length)
    return t


def write_alignment_to_teitok_xml(
    doc: AlignmentDocument,
    path: str | Path,
    *,
    lang_src: str,
    lang_tgt: str,
    title: str | None = None,
    tuid_max_length: int | None = None,
    tuid_prefix: str | None = None,
) -> None:
    """
    Emit a single TEI file: ``<div type="flexalign-import">`` wraps **two** sibling
    ``<div type="flexalign-witness" xml:lang="…">`` columns (pivot/source, then target). Each column
    holds that witness’s ``<s>`` or ``<tok>`` elements in alignment row order; matching ``@tuid`` on
    the two sides links each row. ``xml:lang`` is set on the witness ``div`` only (full BCP47,
    e.g. ``en-US`` / ``vec`` from TMX import metadata); child units do not repeat ``xml:lang`` so the
    tree stays clean for mixed “overall text” + parallel lanes.

    ``tuid_prefix``: when set, each row gets ``{prefix}-s1``, ``-s2``, … (or ``-w{n}`` at
    ``tok`` level) instead of source tuids.

    ``tuid_max_length``: when no prefix, fragments longer than this are replaced with ``t`` + hex.
    ``None`` or ``0`` keeps incoming tuids verbatim.
    """
    path = Path(path)
    nsmap = {None: TEI_NS, "xml": XML_NS}
    root = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=nsmap)
    header = etree.SubElement(root, f"{{{TEI_NS}}}teiHeader")
    fds = etree.SubElement(header, f"{{{TEI_NS}}}fileDesc")
    ts = etree.SubElement(fds, f"{{{TEI_NS}}}titleStmt")
    tit = etree.SubElement(ts, f"{{{TEI_NS}}}title")
    tit.text = title or path.stem
    if doc.version1 or doc.version2:
        notes = etree.SubElement(header, f"{{{TEI_NS}}}notesStmt")
        note = etree.SubElement(notes, f"{{{TEI_NS}}}note")
        note.set("type", "flexalign-witness-paths")
        note.text = f"pivot={doc.version1!r} target={doc.version2!r}"

    text_el = etree.SubElement(root, f"{{{TEI_NS}}}text")
    body = etree.SubElement(text_el, f"{{{TEI_NS}}}body")
    outer = etree.SubElement(body, f"{{{TEI_NS}}}div")
    outer.set("type", "flexalign-import")

    ls = lang_src or "und"
    lt = lang_tgt or "und"

    div_src = etree.SubElement(outer, f"{{{TEI_NS}}}div")
    div_src.set("type", "flexalign-witness")
    div_src.set(f"{{{XML_NS}}}lang", ls)
    div_tgt = etree.SubElement(outer, f"{{{TEI_NS}}}div")
    div_tgt.set("type", "flexalign-witness")
    div_tgt.set(f"{{{XML_NS}}}lang", lt)

    level = (doc.level or "s").strip().lower()
    tag = f"{{{TEI_NS}}}tok" if level == "tok" else f"{{{TEI_NS}}}s"

    idx = 0
    pfx = (tuid_prefix or "").strip()
    for group in doc.alignments:
        for row in group.pairs:
            idx += 1
            if pfx:
                tuid = ordinal_export_tuid(pfx, idx, level=level)
            else:
                tuid = _tuid_for_row(row.tuid_at_write_1, row.tuid_at_write_2, tuid_max_length=tuid_max_length)
            id1 = _primary_anchor(row.id1, f"fa_{idx}_v1")
            id2 = _primary_anchor(row.id2, f"fa_{idx}_v2")

            el1 = etree.SubElement(div_src, tag)
            el1.set(f"{{{XML_NS}}}id", id1)
            if tuid:
                el1.set("tuid", tuid)
            el1.text = row.text1 or ""

            el2 = etree.SubElement(div_tgt, tag)
            el2.set(f"{{{XML_NS}}}id", id2)
            if tuid:
                el2.set("tuid", tuid)
            el2.text = row.text2 or ""

    tree = etree.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="utf-8"))
