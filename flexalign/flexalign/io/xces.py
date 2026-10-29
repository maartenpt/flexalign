"""XCES sentence alignments (OPUS `cesAlign`): read as bitexts; export placeholder.

    <cesAlign version="1.0">
      <linkGrp targType="s" fromDoc="en/ep-00-01-17.xml.gz" toDoc="fr/ep-00-01-17.xml.gz">
        <link xtargets="1 2;1" certainty="0.8"/>     <!-- 2:1 -->
        <link xtargets=";3"/>                         <!-- 0:1, unaligned -->

Each `linkGrp` is one bitext between its two documents; each `link` a bead (`xtargets`: the source unit ids, `;`,
the target unit ids, space-separated). Files may be gzipped and large: read streaming.
"""

from __future__ import annotations

import gzip
from sys import intern
from pathlib import Path
from typing import IO, Iterator, List, Optional, Union

from lxml import etree

from ..align.bitext import Bead, Bitext


def _open(path: Path) -> IO[bytes]:
    with path.open("rb") as f:
        gz = f.read(2) == b"\x1f\x8b"
    return gzip.open(path, "rb") if gz else path.open("rb")


def _local(tag: object) -> str:
    return tag.split("}", 1)[-1] if isinstance(tag, str) else ""


def _doc_name(raw: Optional[str], strip_gz: bool) -> str:
    name = (raw or "").strip()
    return name[:-3] if strip_gz and name.endswith(".gz") else name


def iter_xces(path: Union[str, Path], *, strip_gz: bool = True) -> Iterator[Bitext]:
    """The bitexts of an XCES file, one per `linkGrp`. `strip_gz`: document names without OPUS's `.gz`."""
    path = Path(path)
    current: Optional[Bitext] = None
    with _open(path) as f:
        for event, elem in etree.iterparse(f, events=("start", "end"), load_dtd=False, no_network=True,
                                           resolve_entities=False, huge_tree=True):
            tag = _local(elem.tag)
            if event == "start" and tag == "linkGrp":
                current = Bitext(doc_a=_doc_name(elem.get("fromDoc"), strip_gz),
                                 doc_b=_doc_name(elem.get("toDoc"), strip_gz), source=str(path))
            elif event == "end" and tag == "link" and current is not None:
                xt = elem.get("xtargets") or ""
                if ";" in xt:
                    a, b = xt.split(";", 1)
                    # ids interned: each unit's id string is then held once, not once per bitext that names it
                    current.beads.append(Bead(a=tuple(map(intern, a.split())), b=tuple(map(intern, b.split()))))
                elem.clear()
            elif event == "end" and tag == "linkGrp":
                if current is not None:
                    yield current
                current = None
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]


def read_xces(path: Union[str, Path], *, strip_gz: bool = True) -> List[Bitext]:
    return list(iter_xces(path, strip_gz=strip_gz))


def export_xces(path: Union[str, Path], payload: dict) -> None:
    Path(path).write_text("<xces></xces>\n", encoding="utf-8")
