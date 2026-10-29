"""Compact units for the merge (align/tuid_merge.py): every unit an integer, what the bitexts say in flat arrays.

Units are numbered document by document in (document, unit id) order, so integer order is the order of the
`Unit` tuples: what the merge sorts, and the component roots it picks, are the same as on the tuples. A corpus
the size of Europarl (millions of units, tens of millions of aligned pairs) then fits in memory: an int and a few
array bytes per unit instead of tuples, dicts and sets of tuples.
"""

from __future__ import annotations

from array import array
from collections import defaultdict
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

from .bitext import Bitext, Unit


class UnitIndex:
    """The units of a set of documents, numbered: `docs[d]`'s units are `start[d]` … `start[d + 1] - 1`, in unit
    id order."""

    def __init__(self, units: Dict[str, Set[str]]) -> None:
        self.docs: List[str] = sorted(units)
        self.uids: List[List[str]] = [sorted(units[d]) for d in self.docs]
        self.start = array("q", [0])
        for ids in self.uids:
            self.start.append(self.start[-1] + len(ids))
        self.size = self.start[-1]
        self.doc_number = {d: i for i, d in enumerate(self.docs)}
        self.doc_of = array("i", (d for d, ids in enumerate(self.uids) for _ in ids))
        ranks = list(range(max((len(ids) for ids in self.uids), default=0)))   # one int object per rank, shared
        self._local: Optional[List[Dict[str, int]]] = [dict(zip(ids, ranks)) for ids in self.uids]

    @classmethod
    def of_bitexts(cls, bitexts: Sequence[Bitext], extra: Iterable[Unit] = ()) -> "UnitIndex":
        units: Dict[str, Set[str]] = defaultdict(set)
        for bt in bitexts:
            a, b = units[bt.doc_a], units[bt.doc_b]
            for bead in bt.beads:
                a.update(bead.a)
                b.update(bead.b)
        for doc, uid in extra:
            units[doc].add(uid)
        return cls(units)

    def number(self, doc: int, uid: str) -> int:
        """The unit `uid` of document number `doc` (while the lookup is kept: see `drop_lookup`)."""
        return self.start[doc] + self._local[doc][uid]   # type: ignore[index]

    def numbers(self, doc: int, uids: Iterable[str]) -> Tuple[int, ...]:
        local, base = self._local[doc], self.start[doc]   # type: ignore[index]
        return tuple(base + local[u] for u in uids)

    def drop_lookup(self) -> None:
        """Free the uid → number tables (the merge needs them only while reading the bitexts)."""
        self._local = None

    def unit(self, u: int) -> Unit:
        d = self.doc_of[u]
        return self.docs[d], self.uids[d][u - self.start[d]]

    def uid(self, u: int) -> str:
        d = self.doc_of[u]
        return self.uids[d][u - self.start[d]]


class Constraints:
    """What the bitexts say about a pair of units: per bitext, the bead of each unit of its two documents (-1: not
    in this bitext); the required pairs (two units in one bead) as sorted `u * size + v` numbers (u < v)."""

    def __init__(self, bitexts: Sequence[Bitext], index: UnitIndex,
                 on_bitext: Optional[Callable[[], None]] = None) -> None:
        self.index = index
        n = index.size
        self.doc_a = array("i")
        self.doc_b = array("i")
        self.bead_a: List[array] = []
        self.bead_b: List[array] = []
        self.between: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        pairs = array("q")
        for k, bt in enumerate(bitexts):
            if bt.doc_a == bt.doc_b:
                raise ValueError(f"bitext {bt.source or k}: both sides are {bt.doc_a}")
            da, db = index.doc_number[bt.doc_a], index.doc_number[bt.doc_b]
            sa, sb = index.start[da], index.start[db]
            ba = array("i", [-1]) * (index.start[da + 1] - sa)
            bb = array("i", [-1]) * (index.start[db + 1] - sb)
            for i, bead in enumerate(bt.beads):
                xs = index.numbers(da, bead.a)
                ys = index.numbers(db, bead.b)
                for x in xs:
                    ba[x - sa] = i
                for y in ys:
                    bb[y - sb] = i
                for x in xs:
                    for y in ys:
                        pairs.append(x * n + y if x < y else y * n + x)
            self.doc_a.append(da)
            self.doc_b.append(db)
            self.bead_a.append(ba)
            self.bead_b.append(bb)
            self.between[(da, db) if da < db else (db, da)].append(k)
            if on_bitext:
                on_bitext()
        self.required = _sorted_unique(pairs)

    def pair(self, key: int) -> Tuple[int, int]:
        return divmod(key, self.index.size)

    def key(self, u: int, v: int) -> int:
        return u * self.index.size + v if u < v else v * self.index.size + u

    def bead(self, k: int, u: int) -> int:
        """u's bead in bitext k (-1: none); u must be in one of k's documents."""
        d = self.index.doc_of[u]
        if d == self.doc_a[k]:
            return self.bead_a[k][u - self.index.start[d]]
        return self.bead_b[k][u - self.index.start[d]]

    def bitexts_between(self, du: int, dv: int) -> List[int]:
        return self.between.get((du, dv) if du < dv else (dv, du), [])

    def forbidden(self, u: int, v: int) -> bool:
        du, dv = self.index.doc_of[u], self.index.doc_of[v]
        if du == dv:
            return False
        for k in self.bitexts_between(du, dv):
            bu, bv = self.bead(k, u), self.bead(k, v)
            if bu >= 0 and bv >= 0 and bu != bv:
                return True
        return False

    def known(self, u: int, v: int) -> bool:
        """Some bitext covers both."""
        du, dv = self.index.doc_of[u], self.index.doc_of[v]
        return any(self.bead(k, u) >= 0 and self.bead(k, v) >= 0 for k in self.bitexts_between(du, dv))

    def allowed(self, u: int, v: int, exact: bool) -> bool:
        if self.index.doc_of[u] == self.index.doc_of[v]:
            return True
        if self.forbidden(u, v):
            return False
        return not exact or self.known(u, v)

    def same_doc(self, u: int, v: int) -> bool:
        return self.index.doc_of[u] == self.index.doc_of[v]


def _sorted_unique(values: array) -> array:
    out = array("q")
    last = None
    for x in sorted(values):
        if x != last:
            out.append(x)
            last = x
    return out


def iter_pairs(keys: Iterable[int], size: int) -> Iterator[Tuple[int, int]]:
    for key in keys:
        yield divmod(key, size)
