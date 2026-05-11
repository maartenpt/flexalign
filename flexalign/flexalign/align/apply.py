"""Apply pair/reconcile payloads to XML."""

from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

from .tuid import join_tuids, mint_tuid, parse_tuid

XML_NS = "{http://www.w3.org/XML/1998/namespace}"


def _load_tree(path: Path) -> etree._ElementTree:
    return etree.parse(str(path), etree.XMLParser(remove_blank_text=False, recover=True))


def _find_by_id(root: etree._Element, unit_id: str) -> etree._Element | None:
    results = root.xpath(
        ".//*[@xml:id=$id or @id=$id or @tuid=$id]",
        id=unit_id,
        namespaces={"xml": "http://www.w3.org/XML/1998/namespace"},
    )
    return results[0] if results else None


def _get_tuid(elem: etree._Element | None) -> str | None:
    if elem is None:
        return None
    return elem.get("tuid")


def _set_tuid(elem: etree._Element, value: str) -> None:
    existing = parse_tuid(elem.get("tuid"))
    merged = join_tuids(existing + parse_tuid(value))
    if merged:
        elem.set("tuid", merged)


def _drift_guard(current: str | None, expected: str | None, *, ignore_tuid_drift: bool) -> None:
    if ignore_tuid_drift:
        return
    if expected is None:
        return
    if (current or "").strip() != (expected or "").strip():
        raise ValueError(f"Detected tuid drift: expected={expected!r} current={current!r}")


def _tuids_merged_from_pivot_ids(pivot_root: etree._Element, id1_ids: list) -> str | None:
    """Concatenate unique pivot token ids from @tuid on elements matched by id1 (order-preserving)."""
    merged_parts: list[str] = []
    for raw in id1_ids:
        pivot_node = _find_by_id(pivot_root, str(raw).strip())
        if pivot_node is None:
            continue
        t = _get_tuid(pivot_node)
        if not t:
            continue
        merged_parts.extend(parse_tuid(t))
    out = join_tuids(merged_parts)
    return out if out else None


def _collect_existing_tuids(root: etree._Element) -> set[str]:
    values: set[str] = set()
    for elem in root.xpath(".//*[@tuid]"):
        values.update(parse_tuid(elem.get("tuid")))
    return values


def _handle_invalidation(root: etree._Element, current_tuids: set[str], *, invalidate_below: bool, mark_needs_review: bool) -> None:
    if not invalidate_below and not mark_needs_review:
        return
    for elem in root.xpath(".//*[@tuid]"):
        existing = parse_tuid(elem.get("tuid"))
        if not existing:
            continue
        if any(value not in current_tuids for value in existing):
            if invalidate_below:
                elem.attrib.pop("tuid", None)
            if mark_needs_review:
                elem.set("tuid-needs-review", "true")


def _expected_tuids_from_pair_payload(pair_payload: dict) -> set[str]:
    expected: set[str] = set()
    for group in pair_payload.get("alignments", []):
        parent = group.get("parent", {})
        expected.update(parse_tuid(parent.get("tuid_at_write_1")))
        expected.update(parse_tuid(parent.get("tuid_at_write_2")))
        for row in group.get("pairs", []):
            expected.update(parse_tuid(row.get("tuid_at_write_1")))
            expected.update(parse_tuid(row.get("tuid_at_write_2")))
    return expected


def _resolve_xml_path(raw: str | Path, project_root: Path) -> Path:
    """Resolve pivot/target paths from pair JSON; relative paths are under project_root."""
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def _normalize_pair_doc_paths(pair_payload: dict, project_root: Path) -> None:
    """Rewrite absolute version1/version2 under project_root to project-relative paths (stable with --project-root)."""
    root = project_root.resolve()
    for key in ("version1", "version2"):
        if key not in pair_payload or not isinstance(pair_payload[key], str):
            continue
        raw = pair_payload[key].strip()
        if not raw:
            continue
        p = Path(raw)
        if not p.is_absolute():
            continue
        try:
            resolved = p.resolve()
            rel = resolved.relative_to(root)
            pair_payload[key] = str(rel).replace("\\", "/")
        except ValueError:
            pass


def apply_pair_payload(
    pair_payload: dict,
    *,
    pivot_path: Path,
    project_root: Path | None = None,
    out_dir: Path | None = None,
    ignore_tuid_drift: bool = False,
    invalidate_below: bool = False,
    mark_needs_review: bool = False,
) -> None:
    root = (project_root if project_root is not None else Path.cwd()).resolve()
    _normalize_pair_doc_paths(pair_payload, root)
    pivot_file = _resolve_xml_path(pivot_path, root)
    pivot_tree = _load_tree(pivot_file)
    target_path = _resolve_xml_path(pair_payload["version2"], root)
    target_tree = _load_tree(target_path)
    pivot_root = pivot_tree.getroot()
    target_root = target_tree.getroot()
    minted_index = 1
    id2_slots = 0
    target_writes = 0

    for group in pair_payload.get("alignments", []):
        parent = group.get("parent", {})
        parent_expected = parent.get("tuid_at_write_1")
        parent_ids = parent.get("id1", [])
        if parent_ids:
            pivot_parent = _find_by_id(pivot_root, parent_ids[0])
            _drift_guard(_get_tuid(pivot_parent), parent_expected, ignore_tuid_drift=ignore_tuid_drift)
        for row in group.get("pairs", []):
            expected = row.get("tuid_at_write_1")
            for left in row.get("id1", []):
                pivot_node = _find_by_id(pivot_root, left)
                _drift_guard(_get_tuid(pivot_node), expected, ignore_tuid_drift=ignore_tuid_drift)
            pivot_tuid = (expected or "").strip() or None
            if not pivot_tuid:
                pivot_tuid = _tuids_merged_from_pivot_ids(pivot_root, row.get("id1", []))
            if not pivot_tuid:
                pivot_tuid = mint_tuid("auto", pair_payload.get("level", "s"), minted_index, parent_tuid=parent_expected)
                minted_index += 1
            for right in row.get("id2", []):
                id2_slots += 1
                rid = str(right).strip()
                target_node = _find_by_id(target_root, rid)
                if target_node is not None:
                    _set_tuid(target_node, pivot_tuid)
                    target_writes += 1

    if id2_slots > 0 and target_writes == 0:
        raise ValueError(
            "flexalign apply: matched no target elements for id2 — "
            "check that each id2 matches @xml:id (or @id) on a <tok>/<w> (or other element) in the target file "
            f"({target_path})."
        )

    expected_tuids = _expected_tuids_from_pair_payload(pair_payload)
    allowed_tuids = expected_tuids if expected_tuids else _collect_existing_tuids(target_root)
    _handle_invalidation(
        target_root,
        allowed_tuids,
        invalidate_below=invalidate_below,
        mark_needs_review=mark_needs_review,
    )

    destination = (out_dir / target_path.name) if out_dir else target_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    # TEITOK and similar pipelines store whitespace-sensitive XML; avoid pretty-print reformatting the whole file.
    destination.write_bytes(etree.tostring(target_tree, pretty_print=False, xml_declaration=True, encoding="utf-8"))


def apply_reconciled_payload(payload: dict, *, out_dir: Path | None = None) -> None:
    for item in payload.get("tuids", []):
        tuid = item.get("tuid")
        for doc_path, ids in item.get("members", {}).items():
            path = Path(doc_path)
            tree = _load_tree(path)
            root = tree.getroot()
            for unit_id in ids:
                node = _find_by_id(root, unit_id)
                if node is not None:
                    _set_tuid(node, tuid)
            destination = (out_dir / path.name) if out_dir else path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(etree.tostring(tree, pretty_print=False, xml_declaration=True, encoding="utf-8"))


def apply_from_path(
    *,
    path: Path,
    pivot_path: Path | None = None,
    out_dir: Path | None = None,
    project_root: Path | None = None,
    ignore_tuid_drift: bool = False,
    invalidate_below: bool = False,
    mark_needs_review: bool = False,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "tuids" in payload:
        apply_reconciled_payload(payload, out_dir=out_dir)
    else:
        if pivot_path is None:
            raise ValueError("--pivot is required for pair JSON apply")
        apply_pair_payload(
            payload,
            pivot_path=pivot_path,
            project_root=project_root,
            out_dir=out_dir,
            ignore_tuid_drift=ignore_tuid_drift,
            invalidate_below=invalidate_below,
            mark_needs_review=mark_needs_review,
        )


def apply_pair_tok_refs(
    pair_payload: dict,
    *,
    project_root: Path | None = None,
    out_dir: Path | None = None,
    attr_name: str = "tok",
    reset_target_tok_attr: bool = False,
) -> tuple[int, int]:
    """
    On the target document (version2), set each aligned unit's @tok to the pivot token id(s)
    from id1 (joined with '|' when there are multiple). Pair rows are applied in order; later
    rows overwrite the same id2 as earlier rows.
    """
    root = (project_root if project_root is not None else Path.cwd()).resolve()
    _normalize_pair_doc_paths(pair_payload, root)
    target_path = _resolve_xml_path(pair_payload["version2"], root)
    target_tree = _load_tree(target_path)
    target_root = target_tree.getroot()

    if reset_target_tok_attr:
        for elem in target_root.xpath(".//*[local-name()='tok']"):
            elem.attrib.pop(attr_name, None)

    id2_slots = 0
    target_writes = 0
    for group in pair_payload.get("alignments", []):
        for row in group.get("pairs", []):
            left_ids = [str(x).strip() for x in row.get("id1", []) if str(x).strip()]
            if not left_ids:
                continue
            ref_val = "|".join(left_ids)
            for right in row.get("id2", []):
                id2_slots += 1
                rid = str(right).strip()
                target_node = _find_by_id(target_root, rid)
                if target_node is not None:
                    target_node.set(attr_name, ref_val)
                    target_writes += 1

    if id2_slots > 0 and target_writes == 0:
        raise ValueError(
            "flexalign apply-tok-refs: matched no target elements for id2 — "
            "check that each id2 matches @xml:id (or @id) on an element in the target file "
            f"({target_path})."
        )

    destination = (out_dir / target_path.name) if out_dir else target_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(etree.tostring(target_tree, pretty_print=False, xml_declaration=True, encoding="utf-8"))
    return id2_slots, target_writes


def apply_tok_refs_from_path(
    *,
    path: Path,
    project_root: Path | None = None,
    out_dir: Path | None = None,
    attr_name: str = "tok",
    reset_target_tok_attr: bool = False,
) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return apply_pair_tok_refs(
        payload,
        project_root=project_root,
        out_dir=out_dir,
        attr_name=attr_name,
        reset_target_tok_attr=reset_target_tok_attr,
    )

