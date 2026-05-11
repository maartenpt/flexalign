"""Reconciliation helpers."""

from __future__ import annotations

from lxml import etree
from pathlib import Path

from ..io.jsonio import load_json


def _find_by_id(root: etree._Element, unit_id: str) -> etree._Element | None:
    result = root.xpath(".//*[@xml:id=$id or @id=$id]", id=unit_id, namespaces={"xml": "http://www.w3.org/XML/1998/namespace"})
    return result[0] if result else None


def _validate_drift(pair_payload: dict, *, ignore_tuid_drift: bool) -> None:
    if ignore_tuid_drift:
        return
    version1 = pair_payload.get("version1")
    version2 = pair_payload.get("version2")
    tree1 = etree.parse(str(version1)) if version1 and Path(version1).exists() else None
    tree2 = etree.parse(str(version2)) if version2 and Path(version2).exists() else None
    for group in pair_payload.get("alignments", []):
        parent = group.get("parent", {})
        expected_parent_1 = parent.get("tuid_at_write_1")
        expected_parent_2 = parent.get("tuid_at_write_2")
        for parent_id in parent.get("id1", []):
            if tree1 is not None and expected_parent_1 is not None:
                current = (_find_by_id(tree1.getroot(), parent_id) or etree.Element("empty")).get("tuid")
                if (current or "").strip() != (expected_parent_1 or "").strip():
                    raise ValueError(f"Detected tuid drift for pivot parent {parent_id}: expected={expected_parent_1!r} current={current!r}")
        for parent_id in parent.get("id2", []):
            if tree2 is not None and expected_parent_2 is not None:
                current = (_find_by_id(tree2.getroot(), parent_id) or etree.Element("empty")).get("tuid")
                if (current or "").strip() != (expected_parent_2 or "").strip():
                    raise ValueError(f"Detected tuid drift for target parent {parent_id}: expected={expected_parent_2!r} current={current!r}")
        for row in group.get("pairs", []):
            expected_1 = row.get("tuid_at_write_1")
            expected_2 = row.get("tuid_at_write_2")
            for unit_id in row.get("id1", []):
                if tree1 is not None and expected_1 is not None:
                    current = (_find_by_id(tree1.getroot(), unit_id) or etree.Element("empty")).get("tuid")
                    if (current or "").strip() != (expected_1 or "").strip():
                        raise ValueError(
                            f"Detected tuid drift for pivot node {unit_id}: expected={expected_1!r} current={current!r}"
                        )
            for unit_id in row.get("id2", []):
                if tree2 is not None and expected_2 is not None:
                    current = (_find_by_id(tree2.getroot(), unit_id) or etree.Element("empty")).get("tuid")
                    if (current or "").strip() != (expected_2 or "").strip():
                        raise ValueError(
                            f"Detected tuid drift for target node {unit_id}: expected={expected_2!r} current={current!r}"
                        )


def reconcile_files(paths: list[str], level: str, *, ignore_tuid_drift: bool = False) -> dict:
    members: dict[str, dict[str, list[str]]] = {}
    for path in paths:
        payload = load_json(path)
        _validate_drift(payload, ignore_tuid_drift=ignore_tuid_drift)
        version1 = payload.get("version1")
        version2 = payload.get("version2")
        for group in payload.get("alignments", []):
            for row in group.get("pairs", []):
                tuid = row.get("tuid_at_write_1") or "auto:tuid"
                item = members.setdefault(
                    tuid,
                    {
                        "tuid": tuid,
                        "parent_tuid": group.get("parent", {}).get("tuid_at_write_1"),
                        "members": {},
                        "confidence": row.get("score", 1.0),
                        "needs_review": False,
                    },
                )
                item["members"].setdefault(version1, []).extend(row.get("id1", []))
                item["members"].setdefault(version2, []).extend(row.get("id2", []))
    return {"documents": sorted({doc for item in members.values() for doc in item["members"].keys()}), "level": level, "tuids": list(members.values())}


def reconcile_to_path(paths: list[str], level: str, output: Path, *, ignore_tuid_drift: bool = False) -> dict:
    payload = reconcile_files(paths, level, ignore_tuid_drift=ignore_tuid_drift)
    output.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

