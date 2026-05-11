"""Write minimal TEI/XML with ``<s>`` and optional ``<tok>`` for flexalign backends."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def write_minimal_tei(
    path: str | Path,
    *,
    sentences: list[str],
    token_rows: list[list[str]] | None,
    title: str = "",
    lang: str | None = None,
) -> None:
    """
    Write TEI with one ``<s xml:id=\"s{i}\">`` per sentence.

    If ``token_rows`` is set (same length as ``sentences``), each sentence wraps
    ``<tok xml:id=\"s{i}_w{j}\">`` children; otherwise sentence text is inline only.
    """
    path = Path(path)
    nsmap = {None: TEI_NS, "xml": XML_NS}
    root = etree.Element(f"{{{TEI_NS}}}TEI", nsmap=nsmap)
    header = etree.SubElement(root, f"{{{TEI_NS}}}teiHeader")
    fds = etree.SubElement(header, f"{{{TEI_NS}}}fileDesc")
    ts = etree.SubElement(fds, f"{{{TEI_NS}}}titleStmt")
    tit = etree.SubElement(ts, f"{{{TEI_NS}}}title")
    tit.text = title or path.stem
    text_el = etree.SubElement(root, f"{{{TEI_NS}}}text")
    if lang:
        text_el.set(f"{{{XML_NS}}}lang", lang)
    body = etree.SubElement(text_el, f"{{{TEI_NS}}}body")
    div = etree.SubElement(body, f"{{{TEI_NS}}}div")

    use_tok = token_rows is not None and len(token_rows) == len(sentences)
    for i, sent in enumerate(sentences):
        s_el = etree.SubElement(div, f"{{{TEI_NS}}}s")
        s_el.set(f"{{{XML_NS}}}id", f"s{i}")
        if use_tok:
            toks = token_rows[i] if i < len(token_rows) else []
            for j, form in enumerate(toks):
                tok_el = etree.SubElement(s_el, f"{{{TEI_NS}}}tok")
                tok_el.set(f"{{{XML_NS}}}id", f"s{i}_w{j}")
                tok_el.text = form
        else:
            s_el.text = sent

    tree = etree.ElementTree(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="utf-8"),
    )
