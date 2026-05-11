"""Format-neutral alignment document (IR) with pair / reconcile JSON round-trip."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_PAIR_ROW_KEYS = frozenset(
    {
        "id1",
        "id2",
        "text1",
        "text2",
        "score",
        "edit",
        "tuid_at_write_1",
        "tuid_at_write_2",
    }
)
_TOP_RESERVED = frozenset(
    {
        "version1",
        "version2",
        "level",
        "parent_level",
        "pivot",
        "method",
        "method_detail",
        "mode",
        "notes",
        "alignments",
    }
)


@dataclass
class Witness:
    """One side of a parallel alignment (path + optional BCP47 language)."""

    role: str  # e.g. version1 / version2
    path: str
    lang: str | None = None


@dataclass
class PairRow:
    """One alignment link between pivot and target anchors (pair JSON row)."""

    id1: list[str]
    id2: list[str]
    text1: str = ""
    text2: str = ""
    score: float = 1.0
    edit: str = "auto"
    tuid_at_write_1: str | None = None
    tuid_at_write_2: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id1": list(self.id1),
            "id2": list(self.id2),
            "text1": self.text1,
            "text2": self.text2,
            "score": self.score,
            "edit": self.edit,
            "tuid_at_write_1": self.tuid_at_write_1,
            "tuid_at_write_2": self.tuid_at_write_2,
        }
        out.update(self.extra)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PairRow:
        extra = {k: v for k, v in data.items() if k not in _PAIR_ROW_KEYS}
        return cls(
            id1=[str(x).strip() for x in data.get("id1", []) if str(x).strip()],
            id2=[str(x).strip() for x in data.get("id2", []) if str(x).strip()],
            text1=str(data.get("text1", "") or ""),
            text2=str(data.get("text2", "") or ""),
            score=float(data.get("score", 1.0) or 0.0),
            edit=str(data.get("edit", "auto") or "auto"),
            tuid_at_write_1=data.get("tuid_at_write_1"),
            tuid_at_write_2=data.get("tuid_at_write_2"),
            extra=extra,
        )


@dataclass
class ParentBlock:
    id1: list[str]
    id2: list[str]
    tuid_at_write_1: str | None = None
    tuid_at_write_2: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id1": list(self.id1),
            "id2": list(self.id2),
            "tuid_at_write_1": self.tuid_at_write_1,
            "tuid_at_write_2": self.tuid_at_write_2,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParentBlock:
        return cls(
            id1=[str(x).strip() for x in data.get("id1", []) if str(x).strip()],
            id2=[str(x).strip() for x in data.get("id2", []) if str(x).strip()],
            tuid_at_write_1=data.get("tuid_at_write_1"),
            tuid_at_write_2=data.get("tuid_at_write_2"),
        )


@dataclass
class AlignmentGroup:
    parent: ParentBlock
    pairs: list[PairRow]

    def to_dict(self) -> dict[str, Any]:
        return {"parent": self.parent.to_dict(), "pairs": [p.to_dict() for p in self.pairs]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlignmentGroup:
        parent = ParentBlock.from_dict(data.get("parent") or {})
        pairs = [PairRow.from_dict(row) for row in data.get("pairs", [])]
        return cls(parent=parent, pairs=pairs)


@dataclass
class AlignmentDocument:
    """Canonical alignment IR for a single pivot/target pair."""

    version1: str
    version2: str
    level: str
    parent_level: str | None
    pivot: str
    method: str
    mode: str
    alignments: list[AlignmentGroup]
    method_detail: str | None = None
    notes: list[str] = field(default_factory=list)
    meta_extra: dict[str, Any] = field(default_factory=dict)

    def witnesses(self) -> tuple[Witness, Witness]:
        return (
            Witness("version1", self.version1),
            Witness("version2", self.version2),
        )

    def to_pair_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version1": self.version1,
            "version2": self.version2,
            "level": self.level,
            "parent_level": self.parent_level,
            "pivot": self.pivot,
            "method": self.method,
            "mode": self.mode,
            "alignments": [g.to_dict() for g in self.alignments],
        }
        if self.method_detail is not None:
            payload["method_detail"] = self.method_detail
        if self.notes:
            payload["notes"] = list(self.notes)
        payload.update(self.meta_extra)
        return payload

    @classmethod
    def from_pair_payload(cls, data: dict[str, Any]) -> AlignmentDocument:
        meta_extra = {k: v for k, v in data.items() if k not in _TOP_RESERVED}
        groups = [AlignmentGroup.from_dict(g) for g in data.get("alignments", [])]
        return cls(
            version1=str(data.get("version1", "") or ""),
            version2=str(data.get("version2", "") or ""),
            level=str(data.get("level", "s") or "s"),
            parent_level=data.get("parent_level"),
            pivot=str(data.get("pivot", "version1") or "version1"),
            method=str(data.get("method", "") or ""),
            mode=str(data.get("mode", "direct") or "direct"),
            alignments=groups,
            method_detail=data.get("method_detail"),
            notes=list(data.get("notes") or []),
            meta_extra=meta_extra,
        )

    def to_reconcile_payload(self, *, level: str | None = None) -> dict[str, Any]:
        """Shape compatible with `reconcile_files` output for this single pair."""
        lev = level if level is not None else self.level
        members: dict[str, dict[str, Any]] = {}
        for group in self.alignments:
            parent_tuid = group.parent.tuid_at_write_1
            for row in group.pairs:
                tuid = row.tuid_at_write_1 or "auto:tuid"
                item = members.setdefault(
                    tuid,
                    {
                        "tuid": tuid,
                        "parent_tuid": parent_tuid,
                        "members": {},
                        "confidence": row.score,
                        "needs_review": False,
                    },
                )
                item["members"].setdefault(self.version1, []).extend(row.id1)
                item["members"].setdefault(self.version2, []).extend(row.id2)
        documents = sorted({doc for item in members.values() for doc in item["members"].keys()})
        return {
            "documents": documents,
            "level": lev,
            "tuids": list(members.values()),
        }

    @classmethod
    def from_reconcile_payload(cls, data: dict[str, Any], *, version1: str, version2: str) -> AlignmentDocument:
        """
        Build a pair-shaped IR from a reconcile JSON that references exactly two documents
        (paths must match version1/version2).
        """
        level = str(data.get("level", "s") or "s")
        by_parent: dict[str | None, list[PairRow]] = {}
        for item in data.get("tuids", []):
            tuid = item.get("tuid") or ""
            mem = item.get("members") or {}
            id1 = list(mem.get(version1, []))
            id2 = list(mem.get(version2, []))
            if not id1 and not id2:
                continue
            row = PairRow(
                id1=id1,
                id2=id2,
                text1="",
                text2="",
                score=float(item.get("confidence", 1.0) or 1.0),
                edit="auto",
                tuid_at_write_1=tuid if tuid != "auto:tuid" else None,
                tuid_at_write_2=tuid if tuid != "auto:tuid" else None,
            )
            p_tuid = item.get("parent_tuid")
            by_parent.setdefault(p_tuid, []).append(row)
        alignments: list[AlignmentGroup] = []
        for p_tuid, rows in sorted(by_parent.items(), key=lambda x: (x[0] is not None, str(x[0] or ""))):
            parent = ParentBlock(id1=[], id2=[], tuid_at_write_1=p_tuid, tuid_at_write_2=p_tuid)
            alignments.append(AlignmentGroup(parent=parent, pairs=rows))
        if not alignments:
            alignments.append(AlignmentGroup(parent=ParentBlock(id1=[], id2=[]), pairs=[]))
        return cls(
            version1=version1,
            version2=version2,
            level=level,
            parent_level=None,
            pivot="version1",
            method="reconcile-import",
            mode="direct",
            alignments=alignments,
            method_detail="from-reconcile-json",
            notes=[],
            meta_extra={},
        )

    def compact_tuid_fields(self, *, max_length: int = 56, prefix: str | None = None) -> None:
        """
        Rewrite ``tuid_at_write_*`` in-place.

        If ``prefix`` is set, assign ``{prefix}-s{n}`` (or ``-w{n}`` when ``level`` is ``tok``)
        per row in document order (1-based), ignoring previous values.

        Otherwise, shorten long fragments with ``compact_tuid`` when ``max_length`` > 0.
        """
        from .tuid import compact_tuid, ordinal_export_tuid

        pfx_in = str(prefix or "").strip()
        if pfx_in:
            n = 0
            lv = self.level or "s"
            for group in self.alignments:
                for row in group.pairs:
                    n += 1
                    label = ordinal_export_tuid(pfx_in, n, level=lv)
                    row.tuid_at_write_1 = label
                    row.tuid_at_write_2 = label
            return
        if max_length <= 0:
            return
        for group in self.alignments:
            p = group.parent
            if p.tuid_at_write_1 is not None:
                p.tuid_at_write_1 = compact_tuid(p.tuid_at_write_1, max_length=max_length)
            if p.tuid_at_write_2 is not None:
                p.tuid_at_write_2 = compact_tuid(p.tuid_at_write_2, max_length=max_length)
            for row in group.pairs:
                if row.tuid_at_write_1 is not None:
                    row.tuid_at_write_1 = compact_tuid(row.tuid_at_write_1, max_length=max_length)
                if row.tuid_at_write_2 is not None:
                    row.tuid_at_write_2 = compact_tuid(row.tuid_at_write_2, max_length=max_length)
