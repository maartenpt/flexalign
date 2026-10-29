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

Inside, units are integers and the constraints flat arrays (align/tuid_units.py): Europarl-sized input fits in
memory. The result stays in that form until asked for (`MergeResult.ids`, `members`) or written
(`write_reconcile_payload`, id by id).
"""

from __future__ import annotations

import json
from array import array
from collections import defaultdict
from pathlib import Path
from typing import IO, Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional, Sequence, Set, Tuple, Union

from .bitext import Bitext, Unit
from .tuid_units import Constraints, UnitIndex

POLICIES = ("pivot", "exact")


class MergeResult:
    """The ids: `groups[i]` (units, ascending) is id `names[i]`; per unit its first group in `first` (-1: not
    aligned), further ones in `extra`."""

    def __init__(self, index: UnitIndex, groups: List[List[int]], names: List[str], first: array,
                 extra: Dict[int, List[int]], report: Optional[Dict[str, object]] = None) -> None:
        self.index, self.groups, self.names, self.first, self.extra = index, groups, names, first, extra
        self.report: Dict[str, object] = report or {}
        self._ids: Optional[Dict[Unit, List[str]]] = None

    @property
    def ids(self) -> Dict[Unit, List[str]]:
        """unit → its ids (aligned units only); built on first use."""
        if self._ids is None:
            ids: Dict[Unit, List[str]] = {}
            for u, g in enumerate(self.first):
                if g >= 0:
                    ids[self.index.unit(u)] = [self.names[x] for x in (g, *self.extra.get(u, ()))]
            self._ids = ids
        return self._ids

    @property
    def members(self) -> Dict[str, List[Unit]]:
        """id → its units."""
        return {name: [self.index.unit(u) for u in g] for name, g in zip(self.names, self.groups)}

    @property
    def multivalue(self) -> bool:
        """Whether some unit needs more than one id (the attribute must then be declared multivalue)."""
        return bool(self.extra)


def _pair(u, v):
    return (u, v) if u <= v else (v, u)


def _clean(comp: List[int], cons: Constraints, exact: bool) -> bool:
    """No forbidden pair inside: per bitext, the members it covers on both sides all sit in one bead."""
    doc_of = cons.index.doc_of
    per_bitext: Dict[int, Set[int]] = defaultdict(set)
    sides: Dict[int, Set[int]] = defaultdict(set)
    docs = {doc_of[u] for u in comp}
    for u in comp:
        du = doc_of[u]
        for d in docs:
            if d == du:
                continue
            for k in cons.bitexts_between(du, d):
                b = cons.bead(k, u)
                if b >= 0:
                    per_bitext[k].add(b)
                    sides[k].add(du)
    if any(len(sides[k]) == 2 and len(beads) > 1 for k, beads in per_bitext.items()):
        return False
    if exact:
        return all(cons.same_doc(u, v) or cons.known(u, v) for i, u in enumerate(comp) for v in comp[i + 1:])
    return True


# a bead with both sides: its units in document A, its units in document B
_BeadUnits = Tuple[Tuple[int, ...], Tuple[int, ...]]


def _cover(comp: Set[int], required: Set[Tuple[int, int]], beads: List[_BeadUnits], cons: Constraints,
           exact: bool) -> List[Set[int]]:
    """Cliques covering the component's required pairs, none holding a forbidden pair; few memberships."""
    def valid(clique: Iterable[int]) -> bool:
        c = sorted(clique)
        return all(cons.allowed(u, v, exact) for i, u in enumerate(c) for v in c[i + 1:])

    # start: one clique per bead (a bead holding a contradiction falls back to its pairs)
    cliques: List[Set[int]] = []
    seen: Set[FrozenSet[int]] = set()
    for a, b in beads:
        units = set(a) | set(b)
        if not units <= comp:
            continue
        parts = [units] if valid(units) else [{x, y} for x in a for y in b if _pair(x, y) in required]
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


def _absorb(cliques: List[Set[int]], required: Set[Tuple[int, int]], cons: Constraints,
            exact: bool) -> List[Set[int]]:
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


def _prune(cliques: List[Set[int]], required: Set[Tuple[int, int]]) -> List[Set[int]]:
    """Drop a clique, then a unit in a clique, whose required pairs other cliques already cover."""
    count: Dict[Tuple[int, int], int] = defaultdict(int)
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


def _pairs_in(clique: Set[int], required: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
    c = sorted(clique)
    return [(u, v) for i, u in enumerate(c) for v in c[i + 1:] if (u, v) in required]


def _name(groups: List[List[int]], prefix: str, previous: Optional[Dict[Unit, List[str]]],
          unit: Callable[[int], Unit]) -> List[str]:
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
                for t in previous.get(unit(u), ()):
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


class _Silent:
    """A progress that shows nothing (merge_bitexts without `progress`)."""

    def __init__(self, *_args, **_kw) -> None:   # (label, total=None), as Progress
        pass

    def step(self, *_args, **_kw) -> None:
        pass

    def __enter__(self) -> "_Silent":
        return self

    def __exit__(self, *_) -> None:
        pass


def merge_bitexts(bitexts: List[Bitext], *, policy: str = "pivot", prefix: str = "t",
                  previous: Optional[Dict[Unit, List[str]]] = None, progress: Optional[Callable] = None) -> MergeResult:
    """One tuid system for all the bitexts (see the module docstring). `progress(label, total)`: a context manager
    with `step()` per item of each phase (flexalign.progress.Progress)."""
    if policy not in POLICIES:
        raise ValueError(f"policy: one of {', '.join(POLICIES)}")
    phase = progress or _Silent
    exact = policy == "exact"
    with phase("number units"):
        index = UnitIndex.of_bitexts(bitexts)
    with phase("constraints", len(bitexts)) as p:
        cons = Constraints(bitexts, index, on_bitext=p.step)
    n = index.size
    with phase("contradictions", len(cons.required)) as p:
        contradictions = array("q")
        for key in cons.required:
            p.step()
            u, v = divmod(key, n)
            if cons.forbidden(u, v):
                contradictions.append(key)
    if contradictions:
        dropped = set(contradictions)
        required = array("q", (key for key in cons.required if key not in dropped))
    else:
        required = cons.required

    parent = array("q", range(n))
    linked = bytearray(n)

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    with phase("connect", len(required)) as p:
        for key in required:   # any order: a component's root is always its smallest unit
            p.step()
            u, v = divmod(key, n)
            linked[u] = linked[v] = 1
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[max(ru, rv)] = min(ru, rv)
    comps: Dict[int, List[int]] = defaultdict(list)
    with phase("components", n) as p:
        for u in range(n):
            p.step()
            if linked[u]:
                comps[find(u)].append(u)
    conflicting: Set[int] = set()
    with phase("clean components", len(comps)) as p:
        for root, comp in comps.items():
            p.step()
            if not _clean(comp, cons, exact):
                conflicting.add(root)
    # the conflicting components' required pairs and beads (only they read them)
    req_by_root: Dict[int, Set[Tuple[int, int]]] = defaultdict(set)
    beads_by_root: Dict[int, List[_BeadUnits]] = defaultdict(list)
    if conflicting:
        with phase("conflicting pairs", len(required)) as p:
            for key in required:
                p.step()
                u, v = divmod(key, n)
                root = find(u)
                if root in conflicting:
                    req_by_root[root].add((u, v))
        with phase("conflicting beads", len(bitexts)) as p:
            for bt in bitexts:
                p.step()
                da, db = index.doc_number[bt.doc_a], index.doc_number[bt.doc_b]
                for bead in bt.beads:
                    if not bead.a or not bead.b:
                        continue
                    first = index.number(da, bead.a[0])
                    if linked[first]:
                        root = find(first)
                        if root in conflicting:
                            beads_by_root[root].append((index.numbers(da, bead.a), index.numbers(db, bead.b)))
    index.drop_lookup()

    groups: List[List[int]] = []
    with phase("cover conflicting", len(conflicting)) as p:
        for root in sorted(comps):
            comp = comps[root]
            if root not in conflicting:
                groups.append(comp)
                continue
            p.step()
            groups.extend(sorted(sorted(c) for c in _cover(set(comp), req_by_root[root], beads_by_root[root], cons,
                                                           exact)))
    n_components = len(comps)
    del comps, req_by_root, beads_by_root, parent, linked

    with phase("name ids"):
        names = _name(groups, prefix, previous, index.unit)
    first = array("q", [-1]) * n
    extra: Dict[int, List[int]] = {}
    with phase("ids per unit", len(groups)) as p:
        for gi, g in enumerate(groups):
            p.step()
            for u in g:
                if first[u] < 0:
                    first[u] = gi
                else:
                    extra.setdefault(u, []).append(gi)

    report = _verify(cons, groups, first, extra, exact=exact, phase=phase)
    aligned = sum(1 for g in first if g >= 0)
    report.update({
        "policy": policy,
        "bitexts": len(bitexts),
        "documents": len({d for bt in bitexts for d in (bt.doc_a, bt.doc_b)}),
        "aligned_units": aligned,
        "components": n_components,
        "conflicting_components": len(conflicting),
        "ids": len(groups),
        "units_with_several_ids": len(extra),
        "longest_list": 1 + max(map(len, extra.values())) if extra else (1 if aligned else 0),
        "contradictions": [[list(index.unit(u)), list(index.unit(v))]
                           for u, v in (divmod(key, n) for key in contradictions)],
    })
    result = MergeResult(index, groups, names, first, extra, report)
    if previous is not None:
        ids = result.ids
        report["units_changed"] = sum(1 for u in set(ids) | set(previous)
                                      if sorted(ids.get(u, [])) != sorted(previous.get(u, [])))
    return result


def _verify(cons: Constraints, groups: Sequence[Sequence[int]], first: array, extra: Dict[int, List[int]], *,
            exact: bool, phase: Callable = _Silent) -> Dict[str, object]:
    def groups_of(u: int) -> Set[int]:
        g = first[u]
        return set() if g < 0 else {g, *extra.get(u, ())}

    n = cons.index.size
    with phase("verify pairs", len(cons.required)) as p:
        missing = 0
        for key in cons.required:
            p.step()
            u, v = divmod(key, n)
            if not (groups_of(u) & groups_of(v)) and not cons.forbidden(u, v):
                missing += 1
    wrong: Set[int] = set()
    inferred: Set[int] = set()
    with phase("verify ids", len(groups)) as p:
        for us in groups:
            p.step()
            us = sorted(us)
            for i, u in enumerate(us):
                for v in us[i + 1:]:
                    if cons.same_doc(u, v):
                        continue
                    if cons.forbidden(u, v) or (exact and not cons.known(u, v)):
                        wrong.add(u * n + v)
                    elif not cons.known(u, v):
                        inferred.add(u * n + v)
    return {"ok": not missing and not wrong, "missing_pairs": missing, "forbidden_pairs": len(wrong),
            "inferred_pairs": len(inferred)}


def verify(bitexts: List[Bitext], ids: Dict[Unit, List[str]], *, policy: str = "pivot",
           progress: Optional[Callable] = None) -> Dict[str, object]:
    """Check an assignment against the bitexts: required pairs share an id, forbidden pairs (and, under `exact`,
    pairs no bitext covers) do not. Contradicted pairs (required by one bitext, forbidden by another) are left out."""
    index = UnitIndex.of_bitexts(bitexts, extra=ids)
    cons = Constraints(bitexts, index)
    number: Dict[str, int] = {}
    groups: List[List[int]] = []
    first = array("q", [-1]) * index.size
    extra: Dict[int, List[int]] = {}
    for (doc, uid), names in ids.items():
        u = index.number(index.doc_number[doc], uid)
        for name in names:
            if name not in number:
                number[name] = len(groups)
                groups.append([])
            gi = number[name]
            groups[gi].append(u)
            if first[u] < 0:
                first[u] = gi
            else:
                extra.setdefault(u, []).append(gi)
    return _verify(cons, groups, first, extra, exact=policy == "exact", phase=progress or _Silent)


def iter_reconcile_tuids(result: MergeResult) -> Iterator[Dict[str, object]]:
    """The items of the reconcile format, one per id, its members per document."""
    index = result.index
    for name, units in zip(result.names, result.groups):
        per_doc: Dict[str, List[str]] = {}
        for u in units:
            doc, uid = index.unit(u)
            per_doc.setdefault(doc, []).append(uid)
        yield {"tuid": name, "members": per_doc}


def _payload(result: MergeResult, level: str, tuids: Iterable[Dict[str, object]]) -> Dict[str, object]:
    index = result.index
    docs = [d for i, d in enumerate(index.docs)
            if any(result.first[u] >= 0 for u in range(index.start[i], index.start[i + 1]))]
    return {
        "documents": docs,
        "level": level,
        "assignment": "complete",   # the whole level's ids: apply replaces, not adds
        "multivalue": result.multivalue,
        "tuids": tuids,
        "report": result.report,
    }


def to_reconcile_payload(result: MergeResult, *, level: str = "s") -> Dict[str, object]:
    """The reconcile format (`tuids_<level>.json`): one item per id, its members per document."""
    return _payload(result, level, list(iter_reconcile_tuids(result)))


def write_reconcile_payload(path: Union[str, Path], result: MergeResult, *, level: str = "s",
                            extra: Optional[Dict[str, object]] = None,
                            on_id: Optional[Callable[[], None]] = None) -> None:
    """The reconcile format written id by id (the same bytes as `json.dumps(payload, ensure_ascii=False,
    indent=1)`, without the whole payload in memory); `extra`: more top-level keys after it."""
    def tuids() -> Iterator[Dict[str, object]]:
        for item in iter_reconcile_tuids(result):
            if on_id:
                on_id()
            yield item

    payload = _payload(result, level, tuids())
    payload.update(extra or {})
    with open(path, "w", encoding="utf-8", buffering=1 << 20) as f:
        _dump_streaming(payload, f, stream="tuids")


def _dump_streaming(obj: Dict[str, object], f: IO[str], *, stream: str) -> None:
    """json.dump(obj, indent=1, ensure_ascii=False) with obj[stream] an iterable written item by item."""
    def dumps(x: object) -> str:
        return json.dumps(x, ensure_ascii=False, indent=1)

    if not obj:
        f.write("{}")
        return
    f.write("{")
    for i, (key, value) in enumerate(obj.items()):
        f.write(("," if i else "") + "\n " + json.dumps(key, ensure_ascii=False) + ": ")
        if key == stream:
            wrote = False
            for item in value:   # type: ignore[union-attr]
                f.write(("," if wrote else "[") + "\n" + "\n".join("  " + line for line in dumps(item).split("\n")))
                wrote = True
            f.write("\n ]" if wrote else "[]")
        else:
            f.write(dumps(value).replace("\n", "\n "))
    f.write("\n}")


def from_reconcile_payload(payload: Dict[str, object]) -> Dict[Unit, List[str]]:
    """A previous assignment back from the reconcile format (for an incremental merge)."""
    ids: Dict[Unit, List[str]] = defaultdict(list)
    for item in payload.get("tuids", []):   # type: ignore[union-attr]
        for doc, uids in item.get("members", {}).items():
            for uid in uids:
                ids[(doc, str(uid))].append(item["tuid"])
    return dict(ids)
