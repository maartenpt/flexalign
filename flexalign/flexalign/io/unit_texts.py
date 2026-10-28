"""The units of a document in order, with their text: what unify compares (align/unify.py)."""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import List, Tuple, Union

from lxml import etree


def _local(tag: object) -> str:
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def read_unit_texts(path: Union[str, Path], *, level: str = "s") -> List[Tuple[str, str]]:
    """(id, text) for every `<level>` element with an id (`id` or `xml:id`); the text of its words (OPUS `<w>`,
    TEITOK `<tok>`) or of its content. Gzipped or not."""
    path = Path(path)
    parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False, huge_tree=True)
    with path.open("rb") as f:
        gz = f.read(2) == b"\x1f\x8b"
    if gz:
        with gzip.open(path, "rb") as f:
            root = etree.fromstring(f.read(), parser)
    else:
        root = etree.parse(str(path), parser).getroot()
    out = []
    for el in root.iter():
        if _local(el.tag) != level:
            continue
        uid = el.get("id") or el.get("{http://www.w3.org/XML/1998/namespace}id")
        if uid:
            out.append((uid, " ".join("".join(el.itertext()).split())))
    return out
