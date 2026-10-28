"""Merge any number of bitexts into one tuid system with minimal id lists (dev/TUID-MERGE.md).

Units sharing an id are aligned (pando: `a.tuid = b.tuid` when they share at least one id). The assignment must make
every pair a bead aligns (required) share an id, and no pair a bitext keeps apart (forbidden: covered by the same
bitext, different beads or unaligned) share one. Pairs in one document do not matter; pairs of documents with no
bitext between them are allowed under the `pivot` policy (alignment inferred through other documents) and kept
apart under `exact`.

1. Connected components of the required pairs.
2. A component without a forbidden pair inside gets one id (optimal: every unit one id).
3. Only the other components are covered by several ids: one per bead, merged while no forbidden pair arises, then
   pruned to what is needed.
4. The result is verified against every bitext.

Ids are named `<prefix><n>` in document / unit order. Given a previous assignment, an id keeps its old name when
its members largely survive (an incremental run rewrites only what changed).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .bitext import Bitext, Unit

POLICIES = ("pivot", "exact")


@dataclass
class MergeResult:
    ids: Dict[Unit, List[str]]               # unit → its ids (aligned units only)
    members: Dict[str, List[Unit]]           # id → its units
    report: Dict[str, object] = field(default_factory=dict)

    @property
    def multivalue(self) -> bool:
        """Whether some unit needs more than one id (the attribute must then be declared multivalue)."""
        return any(len(v) > 1 for v in self.ids.values())


class _Constraints:
    """What the bitexts say about a pair of units."""

    def __init__(self, bitexts: List[Bitext]) -> None:
        self.bead_of: List[Dict[Unit, int]] = []                     # per bitext: unit → bead index
        self.between: Dict[FrozenSet[str], List[int]] = defaultdict(list)
        self.required: Set[Tuple[Unit, Unit]] = set()
        for k, bt in enumerate(bitexts):
            if bt.doc_a == bt.doc_b:
                raise ValueError(f"bitext {bt.source or k}: both sides are {bt.doc_a}")
            beads: Dict[Unit, int] = {}
            for i, bead in enumerate(bt.beads):
                for u in bead.a:
                    beads[(bt.doc_a, u)] = i
                for u in bead.b:
                    beads[(bt.doc_b, u)] = i
                for x in bead.a:
                    for y in bead.b:
                        self.required.add(_pair((bt.doc_a, x), (bt.doc_b, y)))
            self.bead_of.append(beads)
            self.between[frozenset((bt.doc_a, bt.doc_b))].append(k)

    def forbidden(self, u: Unit, v: Unit) -> bool:
        if u[0] == v[0]:
            return False
        for k in self.between.get(frozenset((u[0], v[0])), ()):
            bu, bv = self.bead_of[k].get(u), self.bead_of[k].get(v)
            if bu is not None and bv is not None and bu != bv:
                return True
        return False

    def known(self, u: Unit, v: Unit) -> bool:
        """Some bitext covers both."""
        return any(u in self.bead_of[k] and v in self.bead_of[k]
                   for k in self.between.get(frozenset((u[0], v[0])), ()))

    def allowed(self, u: Unit, v: Unit, exact: bool) -> bool:
        if u[0] == v[0]:
            return True
        if self.forbidden(u, v):
            return False
        return not exact or self.known(u, v)


def _pair(u: Unit, v: Unit) -> Tuple[Unit, Unit]:
    return (u, v) if u <= v else (v, u)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: Dict[Unit, Unit] = {}

    def find(self, x: Unit) -> Unit:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: Unit, b: Unit) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _clean(comp: List[Unit], cons: _Constraints, exact: bool) -> bool:
    """No forbidden pair inside: per bitext, the members it covers on both sides all sit in one bead."""
    per_bitext: Dict[int, Set[int]] = defaultdict(set)
    sides: Dict[int, Set[str]] = defaultdict(set)
    docs = {u[0] for u in comp}
    for u in comp:
        for k in (k for d in docs if d != u[0] for k in cons.between.get(frozenset((u[0], d)), ())):
            b = cons.bead_of[k].get(u)
            if b is not None:
                per_bitext[k].add(b)
                sides[k].add(u[0])
    if any(len(sides[k]) == 2 and len(beads) > 1 for k, beads in per_bitext.items()):
        return False
    if exact:
        return all(u[0] == v[0] or cons.known(u, v) for i, u in enumerate(comp) for v in comp[i + 1:])
    return True


# a bead with both sides: (doc A, its units, doc B, its units)
_BeadUnits = Tuple[str, Tuple[str, ...], str, Tuple[str, ...]]


def _cover(comp: Set[Unit], required: Set[Tuple[Unit, Unit]], beads: List[_BeadUnits], cons: _Constraints,
           exact: bool) -> List[Set[Unit]]:
    """Cliques covering the component's required pairs, none holding a forbidden pair; few memberships."""
    def valid(clique: Iterable[Unit]) -> bool:
        c = sorted(clique)
        return all(cons.allowed(u, v, exact) for i, u in enumerate(c) for v in c[i + 1:])

    # start: one clique per bead (a bead holding a contradiction falls back to its pairs)
    cliques: List[Set[Unit]] = []
    seen: Set[FrozenSet[Unit]] = set()
    for doc_a, a, doc_b, b in beads:
        units = {(doc_a, u) for u in a} | {(doc_b, u) for u in b}
        if not units <= comp:
            continue
        parts = [units] if valid(units) else [
            {(doc_a, x), (doc_b, y)} for x in a for y in b if _pair((doc_a, x), (doc_b, y)) in required]
        for p in parts:
            if frozenset(p) not in seen:
                seen.add(frozenset(p))
                cliques.append(set(p))

    # merge cliques that share units while the union stays valid (largest overlap first)
    changed = True
    while changed:
        changed = False
        alive = [i for i, c in enumerate(cliques) if c]
        cand = sorted(((len(cliques[i] & cliques[j]), i, j) for x, i in enumerate(alive) for j in alive[x + 1:]
                       if cliques[i] & cliques[j]), reverse=True)
        for _, i, j in cand:
            ci, cj = cliques[i], cliques[j]
            if not ci or not cj:
                continue
            if all(cons.allowed(x, y, exact) for x in cj - ci for y in ci - cj):
                ci |= cj
                cj.clear()
                changed = True
    cliques = [c for c in cliques if c]

    # two finishes, the smaller kept: prune as merged; or first let each clique absorb the units of an overlapping
    # one it can hold (where a whole bead could not merge, e.g. a 2:1 bead against two 1:1 ones), which may make
    # the original bead redundant
    plain = _prune([set(c) for c in cliques], required)
    absorbed = _prune(_absorb([set(c) for c in cliques], required, cons, exact), required)
    size = lambda cs: (sum(len(c) for c in cs), len(cs))   # noqa: E731
    return absorbed if size(absorbed) < size(plain) else plain


def _absorb(cliques: List[Set[Unit]], required: Set[Tuple[Unit, Unit]], cons: _Constraints,
            exact: bool) -> List[Set[Unit]]:
    """Each clique takes the units of the cliques it overlaps that it can hold and that have a required pair
    into it."""
    out = [set(c) for c in cliques]
    for i, ci in enumerate(out):
        for cj in cliques:
            if cj is cliques[i] or not (ci & cj):
                continue
            for x in sorted(cj - ci):
                if any(_pair(x, y) in required for y in ci) and all(cons.allowed(x, y, exact) for y in ci):
                    ci.add(x)
    return out


def _prune(cliques: List[Set[Unit]], required: Set[Tuple[Unit, Unit]]) -> List[Set[Unit]]:
    """Drop a clique, then a unit in a clique, whose required pairs other cliques already cover."""
    count: Dict[Tuple[Unit, Unit], int] = defaultdict(int)
    for c in cliques:
        for p in _pairs_in(c, required):
            count[p] += 1
    for c in sorted(cliques, key=len):
        ps = _pairs_in(c, required)
        if all(count[p] >= 2 for p in ps):
            for p in ps:
                count[p] -= 1
            c.clear()
    for c in cliques:
        for u in sorted(c):
            ps = [p for p in _pairs_in(c, required) if u in p]
            if len(c) > 2 and all(count[p] >= 2 for p in ps):
                for p in ps:
                    count[p] -= 1
                c.discard(u)
    return [c for c in cliques if _pairs_in(c, required)]


def _pairs_in(clique: Set[Unit], required: Set[Tuple[Unit, Unit]]) -> List[Tuple[Unit, Unit]]:
    c = sorted(clique)
    return [(u, v) for i, u in enumerate(c) for v in c[i + 1:] if (u, v) in required]


def _name(groups: List[List[Unit]], prefix: str, previous: Optional[Dict[Unit, List[str]]]) -> List[str]:
    """Ids for the groups: old names where a group keeps most of an old id's members, else fresh numbers."""
    names: List[Optional[str]] = [None] * len(groups)
    used: Set[str] = set()
    top = 0
    if previous:
        old_members: Dict[str, Set[Unit]] = defaultdict(set)
        for u, ids in previous.items():
            for t in ids:
                old_members[t].add(u)
        for t in old_members:
            if t.startswith(prefix) and t[len(prefix):].isdigit():
                top = max(top, int(t[len(prefix):]))
        scored = []
        for gi, g in enumerate(groups):
            votes: Dict[str, int] = defaultdict(int)
            for u in g:
                for t in previous.get(u, ()):
                    votes[t] += 1
            for t, n in votes.items():
                if 2 * n > len(old_members[t]):   # keeps the majority of the old id's members
                    scored.append((n, gi, t))
        for n, gi, t in sorted(scored, key=lambda x: (-x[0], x[1], x[2])):
            if names[gi] is None and t not in used:
                names[gi] = t
                used.add(t)
    for gi in range(len(groups)):
        if names[gi] is None:
            top += 1
            while f"{prefix}{top}" in used:
                top += 1
            names[gi] = f"{prefix}{top}"
            used.add(names[gi])
    return [n for n in names if n is not None]


def merge_bitexts(bitexts: List[Bitext], *, policy: str = "pivot", prefix: str = "t",
                  previous: Optional[Dict[Unit, List[str]]] = None) -> MergeResult:
    """One tuid system for all the bitexts (see the module docstring)."""
    if policy not in POLICIES:
        raise ValueError(f"policy: one of {', '.join(POLICIES)}")
    exact = policy == "exact"
    cons = _Constraints(bitexts)
    contradictions = sorted(p for p in cons.required if cons.forbidden(*p))
    required = cons.required - set(contradictions)

    uf = _UnionFind()
    for u, v in sorted(required):
        uf.union(u, v)
    comps: Dict[Unit, List[Unit]] = defaultdict(list)
    for u in sorted(uf.parent):
        comps[uf.find(u)].append(u)
    # per component: its required pairs and beads (only the conflicting ones read them)
    req_by_root: Dict[Unit, Set[Tuple[Unit, Unit]]] = defaultdict(set)
    for p in required:
        req_by_root[uf.find(p[0])].add(p)
    beads_by_root: Dict[Unit, List[_BeadUnits]] = defaultdict(list)
    for bt in bitexts:
        for bead in bt.beads:
            first = (bt.doc_a, bead.a[0]) if bead.a else None
            if bead.b and first in uf.parent:
                beads_by_root[uf.find(first)].append((bt.doc_a, bead.a, bt.doc_b, bead.b))

    groups: List[List[Unit]] = []
    conflicting = 0
    for root in sorted(comps):
        comp = comps[root]
        if _clean(comp, cons, exact):
            groups.append(comp)
            continue
        conflicting += 1
        groups.extend(sorted(sorted(c) for c in _cover(set(comp), req_by_root[root], beads_by_root[root], cons,
                                                       exact)))

    names = _name(groups, prefix, previous)
    ids: Dict[Unit, List[str]] = defaultdict(list)
    members: Dict[str, List[Unit]] = {}
    for name, g in zip(names, groups):
        members[name] = g
        for u in g:
            ids[u].append(name)

    report = verify(bitexts, ids, policy=policy)
    report.update({
        "policy": policy,
        "bitexts": len(bitexts),
        "documents": len({d for bt in bitexts for d in (bt.doc_a, bt.doc_b)}),
        "aligned_units": len(ids),
        "components": len(comps),
        "conflicting_components": conflicting,
        "ids": len(members),
        "units_with_several_ids": sum(1 for v in ids.values() if len(v) > 1),
        "longest_list": max((len(v) for v in ids.values()), default=0),
        "contradictions": [[list(u), list(v)] for u, v in contradictions],
    })
    if previous is not None:
        report["units_changed"] = sum(1 for u in set(ids) | set(previous)
                                      if sorted(ids.get(u, [])) != sorted(previous.get(u, [])))
    return MergeResult(ids=dict(ids), members=members, report=report)


def verify(bitexts: List[Bitext], ids: Dict[Unit, List[str]], *, policy: str = "pivot") -> Dict[str, object]:
    """Check an assignment against the bitexts: required pairs share an id, forbidden pairs (and, under `exact`,
    pairs no bitext covers) do not. Contradicted pairs (required by one bitext, forbidden by another) are left out."""
    cons = _Constraints(bitexts)
    exact = policy == "exact"
    shared = lambda u, v: bool(set(ids.get(u, ())) & set(ids.get(v, ())))   # noqa: E731
    missing = [p for p in cons.required if not cons.forbidden(*p) and not shared(*p)]
    members: Dict[str, List[Unit]] = defaultdict(list)
    for u, ts in ids.items():
        for t in ts:
            members[t].append(u)
    wrong, inferred = set(), set()
    for us in members.values():
        us = sorted(us)
        for i, u in enumerate(us):
            for v in us[i + 1:]:
                if u[0] == v[0]:
                    continue
                if cons.forbidden(u, v) or (exact and not cons.known(u, v)):
                    wrong.add((u, v))
                elif not cons.known(u, v):
                    inferred.add((u, v))
    return {"ok": not missing and not wrong, "missing_pairs": len(missing), "forbidden_pairs": len(wrong),
            "inferred_pairs": len(inferred)}


def to_reconcile_payload(result: MergeResult, *, level: str = "s") -> Dict[str, object]:
    """The reconcile format (`tuids_<level>.json`): one item per id, its members per document."""
    tuids = []
    for name, units in result.members.items():
        per_doc: Dict[str, List[str]] = defaultdict(list)
        for doc, uid in units:
            per_doc[doc].append(uid)
        tuids.append({"tuid": name, "members": dict(per_doc)})
    return {
        "documents": sorted({u[0] for u in result.ids}),
        "level": level,
        "multivalue": result.multivalue,
        "tuids": tuids,
        "report": result.report,
    }


def from_reconcile_payload(payload: Dict[str, object]) -> Dict[Unit, List[str]]:
    """A previous assignment back from the reconcile format (for an incremental merge)."""
    ids: Dict[Unit, List[str]] = defaultdict(list)
    for item in payload.get("tuids", []):   # type: ignore[union-attr]
        for doc, uids in item.get("members", {}).items():
            for uid in uids:
                ids[(doc, str(uid))].append(item["tuid"])
    return dict(ids)
