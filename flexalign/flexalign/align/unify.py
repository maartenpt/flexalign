"""Unify copies of one document before a merge (dev/TUID-MERGE.md, "unit identification").

Bitext collections can hold several copies of the same document, one per bitext (OPUS keeps a copy of the pivot
document per language pair). Then the same sentence has a unit in every copy and the bitexts never meet. Given
which copies belong together (the caller knows: file naming, a manifest), this maps every copy's units onto one
canonical document:

1. the copy with the most units is the canonical one; its units are kept as they are;
2. a unit of another copy with the same id and the same text is that unit;
3. with `text_fallback`, a unit still unmatched is matched by identical text, in document order (the next
   canonical unit with that text after the last match), for copies that were renumbered;
4. a unit found nowhere becomes an extra unit of the canonical document, placed after the canonical unit its
   predecessor maps to (reported, so the caller can insert it in the document);
5. a copy that matches less than `min_overlap` of its units is no copy but another version (other orthography,
   other selection): it stays a document of its own, under its own name (reported as `separate`).

Text is compared NFC-normalised without whitespace (copies differ in spacing, not in words). An id whose text
differs is not merged. The bitexts are then rewritten onto the canonical units (`rewrite_bitexts`).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .bitext import Bead, Bitext, Unit

_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    return _WS.sub("", unicodedata.normalize("NFC", text))


@dataclass
class Extra:
    """A unit of a copy that the canonical document lacks."""

    unit: Unit                 # its new unit in the canonical document
    source: Unit               # where it comes from (copy document, id)
    after: Optional[str]       # the canonical unit it follows (None: at the start)


@dataclass
class Unification:
    id_map: Dict[Unit, Unit] = field(default_factory=dict)     # copy unit → canonical unit
    extras: Dict[str, List[Extra]] = field(default_factory=dict)
    report: Dict[str, Dict[str, object]] = field(default_factory=dict)   # per canonical document


def unify_copies(groups: Dict[str, Sequence[str]], texts: Dict[str, List[Tuple[str, str]]], *,
                 text_fallback: bool = False, min_overlap: float = 0.5) -> Unification:
    """`groups`: canonical document name → its copies (document names as the bitexts use them); `texts`: per copy,
    its units in order as (id, text)."""
    out = Unification()
    for canonical, copies in groups.items():
        copies = [c for c in copies if c in texts]
        if not copies:
            continue
        base = max(copies, key=lambda c: (len(texts[c]), [-ord(ch) for ch in c]))
        base_units = texts[base]
        order = {uid: i for i, (uid, _) in enumerate(base_units)}
        by_id = {uid: normalise(t) for uid, t in base_units}
        by_text: Dict[str, List[str]] = {}
        for uid, t in base_units:
            by_text.setdefault(normalise(t), []).append(uid)
        for uid, _ in base_units:
            out.id_map[(base, uid)] = (canonical, uid)
        rep: Dict[str, object] = {"canonical_copy": base, "units": len(base_units), "copies": {}}
        taken_ids = set(by_id)
        for copy in copies:
            if copy == base:
                continue
            stats: Dict[str, object] = {"units": len(texts[copy]), "by_id": 0, "by_text": 0, "extra": 0,
                                        "id_text_differs": 0}
            mapping: Dict[Unit, Unit] = {}
            extras: List[Extra] = []
            new_ids: List[str] = []
            last = -1          # position in the canonical copy of the last match
            prev: Optional[str] = None
            for uid, t in texts[copy]:
                nt = normalise(t)
                target: Optional[str] = None
                if by_id.get(uid) == nt:
                    target = uid
                    stats["by_id"] += 1
                else:
                    if uid in by_id:
                        stats["id_text_differs"] += 1
                    if text_fallback:
                        after = [c for c in by_text.get(nt, []) if order[c] > last]
                        if after:
                            target = after[0]
                            stats["by_text"] += 1
                if target is not None:
                    mapping[(copy, uid)] = (canonical, target)
                    last = max(last, order[target])
                    prev = target
                    continue
                new_id = uid
                n = 1
                while new_id in taken_ids or new_id in new_ids:
                    n += 1
                    new_id = f"{uid}_{n}"
                new_ids.append(new_id)
                mapping[(copy, uid)] = (canonical, new_id)
                extras.append(Extra((canonical, new_id), (copy, uid), prev))
                stats["extra"] += 1
                prev = new_id
            matched = stats["by_id"] + stats["by_text"]   # type: ignore[operator]
            if texts[copy] and matched < min_overlap * len(texts[copy]):
                stats["separate"] = True   # another version: its own document, as it is
            else:
                out.id_map.update(mapping)
                if extras:
                    out.extras.setdefault(canonical, []).extend(extras)
                taken_ids.update(new_ids)
            rep["copies"][copy] = stats   # type: ignore[index]
        out.report[canonical] = rep
    return out


def rewrite_bitexts(bitexts: List[Bitext], unification: Unification) -> List[Bitext]:
    """The bitexts on the canonical units (documents not in any group are left as they are)."""
    out = []
    for bt in bitexts:
        def side(doc: str, ids: Tuple[str, ...]) -> Tuple[str, Tuple[str, ...]]:
            mapped = [unification.id_map.get((doc, u)) for u in ids]
            if not ids or any(m is None for m in mapped):
                if any(m is not None for m in mapped):
                    raise ValueError(f"{doc}: a bead mixes unified and unknown units ({ids})")
                return doc, ids
            docs = {m[0] for m in mapped if m}
            if len(docs) != 1:
                raise ValueError(f"{doc}: a bead's units map to several documents")
            return docs.pop(), tuple(dict.fromkeys(m[1] for m in mapped if m))

        doc_a = doc_b = None
        beads = []
        for bead in bt.beads:
            da, a = side(bt.doc_a, bead.a)
            db, b = side(bt.doc_b, bead.b)
            doc_a = doc_a or (da if bead.a else None)
            doc_b = doc_b or (db if bead.b else None)
            beads.append(Bead(a, b))
        a_name = doc_a or _doc_of(bt.doc_a, unification)
        b_name = doc_b or _doc_of(bt.doc_b, unification)
        out.append(Bitext(a_name, b_name, beads, bt.source))
    return out


def _doc_of(doc: str, unification: Unification) -> str:
    for (d, _), (canonical, _) in unification.id_map.items():
        if d == doc:
            return canonical
    return doc
