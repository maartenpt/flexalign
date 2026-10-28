"""flexalign pair JSON (`flexalign align` output) read as a bitext: one bead per row of every alignment group.

Rows sharing a unit are one bead (word aligners give an n:m link as several word pairs). Documents are named by
`version1` / `version2`, relative to `doc_root` when they lie under it (the names `flexalign apply --project-root`
resolves).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ..align.bitext import Bead, Bitext


def _doc_name(raw: str, doc_root: Optional[Path]) -> str:
    if doc_root is None:
        return raw
    try:
        return Path(raw).resolve().relative_to(doc_root.resolve()).as_posix()
    except ValueError:
        return raw


def read_pair_bitext(path: Union[str, Path], *, doc_root: Optional[Path] = None) -> Bitext:
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    bt = Bitext(doc_a=_doc_name(str(payload["version1"]), doc_root),
                doc_b=_doc_name(str(payload["version2"]), doc_root), source=str(path))
    parent: Dict[Tuple[int, str], Tuple[int, str]] = {}

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u

    for group in payload.get("alignments", []):
        for row in group.get("pairs", []):
            if row.get("edit") == "negative":   # a link someone rejected: not a bead
                continue
            units = [(0, str(x)) for x in row.get("id1", [])] + [(1, str(x)) for x in row.get("id2", [])]
            for u in units:
                parent.setdefault(u, u)
            for u in units[1:]:
                parent[find(u)] = find(units[0])
    beads: Dict[Tuple[int, str], List[Tuple[int, str]]] = {}
    for u in parent:   # insertion order: the order of the rows
        beads.setdefault(find(u), []).append(u)
    for units in beads.values():
        bt.beads.append(Bead(a=tuple(x for side, x in units if side == 0), b=tuple(x for side, x in units if side == 1)))
    return bt
