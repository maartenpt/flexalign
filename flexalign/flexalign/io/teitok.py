"""TEITOK IO helpers."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from ..align.align_doc import AlignDoc


def load_teitok(path: str | Path) -> AlignDoc:
    return AlignDoc.from_file(path)


def save_teitok(doc: AlignDoc, path: str | Path) -> None:
    Path(path).write_bytes(etree.tostring(doc.tree, pretty_print=True, xml_declaration=True, encoding="utf-8"))

