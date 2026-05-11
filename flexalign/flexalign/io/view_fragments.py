"""Read-only TEI fragment extraction for viewers (tuview, editors).

Operates on on-disk XML only; returns compact JSON-friendly rows. Alignment spine =
elements at the chosen TEI level that carry ``@tuid`` (optionally extended later).

**Empty ``<s/>`` + ``@sameAs`` (TEITOK-style overlap):** TEITOK often exposes a *string cut-out*
from the serialized ``<s …/>`` through the **end of the last referenced token**, which may
stop *inside* a wrapper (e.g. before ``</add>``) and is therefore **not guaranteed to be a
single well-formed XML document**. Flexalign concatenates ``tostring(<s/>)`` with the
serialization of each **top-level sibling** of ``<s>`` from the first sibling that contains
the first ``sameAs`` id through the sibling that contains the last id
(see :func:`_sameas_following_top_slice`). On a **deep copy** of that sibling span, we then
**prune** everything that follows the last matched id *inside the final top-level sibling*
(:func:`_sameas_prune_after_within_top`), so trailing ``<tok>`` / notes after the sentence’s
last token are dropped while each emitted piece stays well-formed. TEITOK’s exact byte
fragment can still differ (e.g. they may truncate mid-tag); matching that would need their
offset logic or a dedicated partial serializer.

Performance: the default implementation scans TEI with lxml. For production latency on
large files, a future backend may delegate to **flexicorp-pando** / **xidx** byte-offset
indexes (same JSON contract). See ``dev/tuview-design.md`` §2.3.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from lxml import etree

from .alignment_sets import resolve_alignment_set_members_detailed

_NS_XML = "http://www.w3.org/XML/1998/namespace"


def level_to_local_tag(level: str) -> str:
    """Map viewer level names to TEI local names (subset — extend as needed)."""
    normalized = (level or "s").strip().lower()
    mapping = {
        "text": "text",
        "chapter": "div",
        "div": "div",
        "ab": "ab",
        "p": "p",
        "s": "s",
        "tok": "tok",
    }
    return mapping.get(normalized, normalized)


def _load_tree(path: Path) -> etree._ElementTree:
    parser = etree.XMLParser(remove_blank_text=False, recover=True)
    return etree.parse(str(path), parser)


def extract_embedded_css(tree: etree._ElementTree) -> str:
    """Collect inline CSS from TEI sources used by viewer rendering.

    Sources:
    - ``<style>`` blocks
    - ``<tagsDecl><rendition scheme="css">...``
    """
    root = tree.getroot()
    chunks: list[str] = []
    for elem in root.xpath(".//*[local-name()='style']"):
        txt = (elem.text or "").strip()
        if txt:
            chunks.append(txt)
        for child in elem:
            if child.tail:
                chunks.append(child.tail.strip())
    for elem in root.xpath(
        ".//*[local-name()='tagsDecl']/*[local-name()='rendition' and "
        "(not(@scheme) or translate(normalize-space(@scheme), "
        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='css')]"
    ):
        txt = " ".join(elem.itertext()).strip()
        if txt:
            chunks.append(txt)
    return "\n\n".join(c for c in chunks if c)


def _element_identity(elem: etree._Element) -> str:
    return (
        elem.get(f"{{{_NS_XML}}}id") or elem.get("id") or elem.get("tuid") or ""
    ).strip()


def _local_tag(elem: etree._Element) -> str:
    tag = elem.tag
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        return tag.split("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


# Inline TEI elements rendered as structured wraps (not flattened to plain text).
_WRAP_INLINE_TAGS = frozenset(
    {
        "del",
        "add",
        "hi",
        "emph",
        "sic",
        "corr",
        "supplied",
        "unclear",
        "damage",
        "subst",
        "orig",
        "reg",
        "expan",
        "abbr",
        "foreign",
        "gap",
        "lb",
        "pb",
    }
)


def _merge_adjacent_text_segments(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for p in parts:
        if p.get("kind") == "text" and merged and merged[-1].get("kind") == "text":
            merged[-1]["text"] = (merged[-1].get("text") or "") + (p.get("text") or "")
        else:
            merged.append(p)
    return merged


def diplomatic_segments(elem: etree._Element, note_local: str = "note") -> list[dict[str, Any]]:
    """Ordered segments: ``text``, ``note``, and nested ``wrap`` (``del``, ``add``, …) preserving markup."""
    note_cf = note_local.casefold()

    def walk(el: etree._Element) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        if el.text:
            parts.append({"kind": "text", "text": el.text})
        for child in el:
            tag = _local_tag(child).casefold()
            if tag == note_cf:
                nt = " ".join(child.itertext()).strip()
                if nt:
                    parts.append({"kind": "note", "text": nt})
                if child.tail:
                    parts.append({"kind": "text", "text": child.tail})
            elif tag in _WRAP_INLINE_TAGS:
                inner = walk(child)
                parts.append({"kind": "wrap", "tag": tag, "segments": inner})
                if child.tail:
                    parts.append({"kind": "text", "text": child.tail})
            else:
                inner = walk(child)
                parts.extend(inner)
                if child.tail:
                    parts.append({"kind": "text", "text": child.tail})
        return _merge_adjacent_text_segments(parts)

    out = walk(elem)
    return [s for s in out if not (s.get("kind") == "text" and (s.get("text") or "") == "")]


def plain_text_from_rich_segments(segments: list[dict[str, Any]]) -> str:
    """Whitespace-normalised plain summary (note bodies omitted; wraps flattened by concatenating text runs).

    Adjacent text leaves are joined without inserting spaces so ``some<del>one</del>thing`` → ``something``.
    """
    parts: list[str] = []

    def flatten(seglist: list[dict[str, Any]]) -> None:
        for seg in seglist:
            k = seg.get("kind")
            if k == "text":
                parts.append(str(seg.get("text") or ""))
            elif k == "wrap":
                flatten(list(seg.get("segments") or []))

    flatten(segments)
    joined = "".join(parts)
    return " ".join(joined.split())


def segments_with_notes_inline(elem: etree._Element, note_local: str = "note") -> list[dict[str, Any]]:
    """Backward-compatible name — delegates to :func:`diplomatic_segments`."""
    return diplomatic_segments(elem, note_local=note_local)


def plain_text_from_segments(segments: list[dict[str, Any]]) -> str:
    """Whitespace-normalised plain line without note bodies (for search / summaries)."""
    return plain_text_from_rich_segments(segments)


def _serialize_aligned_element(elem: etree._Element) -> str:
    """Pretty-printed outer XML for one aligned unit (side-by-side raw view)."""
    return etree.tostring(elem, encoding="unicode", pretty_print=True)


def _sameas_ref_id_list(elem: etree._Element) -> list[str]:
    """Parse TEI ``@sameAs`` / TEITOK ``@sameas`` into local id tokens (``#w-1`` → ``w-1``)."""
    raw = (elem.get("sameAs") or elem.get("sameas") or "").strip()
    if not raw:
        return []
    out: list[str] = []
    for part in raw.replace(",", " ").split():
        p = part.strip()
        if not p:
            continue
        if p.startswith("#"):
            p = p[1:]
        if p:
            out.append(p)
    return out


def _elem_identity_for_sameas(el: etree._Element) -> str:
    """Resolve ``xml:id``, HTML ``id``, or ``@tuid`` (TEITOK ``<tok id=…>``)."""
    return (
        el.get(f"{{{_NS_XML}}}id")
        or el.get("id")
        or el.get("tuid")
        or ""
    ).strip()


def _sameas_follower_elements(elem: etree._Element, ids: list[str]) -> list[etree._Element]:
    """Collect leaf elements whose ids appear in ``@sameAs``, in **document order** after ``elem``.

    Used to locate the span of real content (which may sit under ``<add>``, etc.). The actual
    expansion uses :func:`_sameas_following_top_slice` so wrappers, notes, and element tails
    are kept—not only a flattened list of ``<tok>`` nodes.
    """
    if not ids:
        return []
    parent = elem.getparent()
    if parent is None:
        return []
    collected: list[etree._Element] = []
    want_idx = 0
    for sib in elem.itersiblings(preceding=False):
        for node in sib.iter():
            if want_idx >= len(ids):
                break
            if _elem_identity_for_sameas(node) == ids[want_idx]:
                collected.append(node)
                want_idx += 1
        if want_idx >= len(ids):
            break
    return collected


def _sameas_following_top_slice(elem: etree._Element, ids: list[str]) -> list[etree._Element]:
    """Top-level siblings under ``elem``'s parent from the first to the last ``@sameAs`` hit (inclusive).

    Preserves ``<add>``, ``<note>``, ``<hi>``, and other markup between empty ``<s/>`` and the
    sentence's trailing tokens—unlike concatenating only the matched leaf nodes.

    **Versus TEITOK:** TEITOK’s viewer fragment may end at the **last id-matched token** even
    when that yields invalid XML. We take whole top-level siblings for that span, then prune
    after the last id inside the copied **last** sibling so the emitted subtree is still
    well-formed XML per root.
    """
    followers = _sameas_follower_elements(elem, ids)
    if not followers:
        return []
    parent = elem.getparent()
    if parent is None:
        return []

    def top_under_parent(child: etree._Element) -> etree._Element:
        cur = child
        while cur is not None and cur.getparent() is not None and cur.getparent() is not parent:
            cur = cur.getparent()
        return cur

    start_top = top_under_parent(followers[0])
    end_top = top_under_parent(followers[-1])
    children = list(parent)
    try:
        i_s = children.index(start_top)
        i_e = children.index(end_top)
    except ValueError:
        return []
    if i_s > i_e:
        i_s, i_e = i_e, i_s
    return children[i_s : i_e + 1]


def _sameas_corresponding_descendant(
    copy_root: etree._Element, orig_root: etree._Element, orig_target: etree._Element
) -> etree._Element | None:
    """Locate the node in ``copy_root`` that mirrors ``orig_target`` under ``orig_root`` (same child indices)."""
    if copy_root is None or orig_root is None or orig_target is None:
        return None
    if orig_target is orig_root:
        return copy_root
    idxs: list[int] = []
    cur: etree._Element | None = orig_target
    while cur is not None and cur is not orig_root:
        parent = cur.getparent()
        if parent is None:
            return None
        sibs = list(parent)
        try:
            idxs.append(sibs.index(cur))
        except ValueError:
            return None
        cur = parent
    idxs.reverse()
    out: etree._Element = copy_root
    for i in idxs:
        ch = list(out)
        if i < 0 or i >= len(ch):
            return None
        out = ch[i]
    return out


def _sameas_prune_after_within_top(top_copy: etree._Element, last_desc: etree._Element) -> None:
    """Drop document-order content after ``last_desc`` within subtree ``top_copy`` (mutates ``top_copy``).

    Removes following element siblings along the path from ``last_desc`` up to (but not past)
    ``top_copy``, and clears ``last_desc.tail`` so text after the last matched token is not
    kept.
    """
    if last_desc.getparent() is None:
        return
    cur: etree._Element | None = last_desc
    while cur is not None and cur is not top_copy:
        parent = cur.getparent()
        if parent is None:
            break
        seen = False
        for sib in list(parent):
            if sib is cur:
                seen = True
                continue
            if seen:
                parent.remove(sib)
        cur = parent
    last_desc.tail = None


def _expand_sameas_if_empty_sentence(
    elem: etree._Element,
    segments: list[dict[str, Any]],
    text: str,
    xml: str,
) -> tuple[list[dict[str, Any]], str, str]:
    """When an aligned unit is text-empty but lists ``@sameAs``, fold in those nodes for xml/segments/text.

    The returned ``xml`` is ``tostring(<s/>)`` plus the serialization of a **deep copy** of
    the top-level sibling span from :func:`_sameas_following_top_slice`, after pruning
    everything that follows the last ``sameAs`` id inside the **last** of those siblings
    (:func:`_sameas_prune_after_within_top`). That hides redundant markup after the last
    matched token while keeping each root well-formed. Multiple roots in one string are
    still possible (``<s/>`` + one or more siblings).
    """
    if text.strip():
        return segments, text, xml
    ids = _sameas_ref_id_list(elem)
    if not ids:
        return segments, text, xml
    followers = _sameas_follower_elements(elem, ids)
    if not followers:
        return segments, text, xml
    slice_els = _sameas_following_top_slice(elem, ids)
    if not slice_els:
        return segments, text, xml
    slice_copies = [deepcopy(ch) for ch in slice_els]
    last_orig = followers[-1]
    tail_orig = slice_els[-1]
    tail_copy = slice_copies[-1]
    last_copy = _sameas_corresponding_descendant(tail_copy, tail_orig, last_orig)
    if last_copy is not None:
        _sameas_prune_after_within_top(tail_copy, last_copy)
    # Synthetic parent: one walk so tails between siblings and inline TEI (``add``, ``note``, …) survive.
    wrap = etree.Element("tuview-sameas-expand")
    for ch in slice_copies:
        wrap.append(ch)
    merged_segments = diplomatic_segments(wrap, "note")
    merged_segments = _merge_adjacent_text_segments(merged_segments)
    merged_segments = [
        s
        for s in merged_segments
        if not (s.get("kind") == "text" and (s.get("text") or "") == "")
    ]
    new_text = plain_text_from_rich_segments(merged_segments)
    if not new_text.strip():
        return segments, text, xml
    # Tight serialization (no pretty_print): avoids newlines between ``<s/>`` and the following slice
    # that some HTML contexts treat as inter-word space.
    new_xml = etree.tostring(elem, encoding="unicode", pretty_print=False).strip() + "".join(
        etree.tostring(ch, encoding="unicode", pretty_print=False) for ch in slice_copies
    )
    return merged_segments, new_text, new_xml


def iter_aligned_units_for_level(path: Path, level: str) -> list[dict[str, Any]]:
    """Return aligned units at ``level`` (elements with ``@tuid``), document order."""
    tag = level_to_local_tag(level)
    tree = _load_tree(path)
    root = tree.getroot()
    xpath = f".//*[local-name()='{tag}' and @tuid]"
    rows: list[dict[str, Any]] = []
    for elem in root.xpath(xpath):
        tuid = (elem.get("tuid") or "").strip()
        uid = _element_identity(elem)
        segments = diplomatic_segments(elem, "note")
        text = plain_text_from_rich_segments(segments)
        xml = _serialize_aligned_element(elem)
        segments, text, xml = _expand_sameas_if_empty_sentence(elem, segments, text, xml)
        row: dict[str, Any] = {
            "tuid": tuid,
            "id": uid,
            "text": text,
            "source_file": str(path),
            "xml": xml,
            "segments": segments,
        }
        rows.append(row)
    return rows


def _serialize_between_aligned_bounds(
    path: Path,
    level: str,
    start_idx: int,
    end_idx: int,
    *,
    include_from_start: bool = False,
) -> str:
    """Serialize XML window bounded by aligned units in one file.

    ``bounded`` mode (default): include running XML from first aligned unit to last aligned unit,
    including non-aligned material between them.
    ``from_start`` mode (``include_from_start=True``): include from start of ``<text>``/``<body>``
    to the last aligned unit.
    """
    if end_idx < start_idx:
        return ""
    tag = level_to_local_tag(level)
    tree = _load_tree(path)
    root = tree.getroot()
    aligned = root.xpath(f".//*[local-name()='{tag}' and @tuid]")
    if not aligned:
        return ""
    start_idx = max(0, min(start_idx, len(aligned) - 1))
    end_idx = max(0, min(end_idx, len(aligned) - 1))
    if end_idx < start_idx:
        start_idx, end_idx = end_idx, start_idx

    start_elem = aligned[start_idx]
    end_elem = aligned[end_idx]

    def _ancestor_chain(elem: etree._Element) -> list[etree._Element]:
        chain: list[etree._Element] = []
        cur: etree._Element | None = elem
        while cur is not None:
            chain.append(cur)
            cur = cur.getparent()
        return chain

    def _lowest_common_ancestor(a: etree._Element, b: etree._Element) -> etree._Element:
        a_chain = _ancestor_chain(a)
        b_set = set(_ancestor_chain(b))
        for node in a_chain:
            if node in b_set:
                return node
        return root

    def _first_top_child_under(container: etree._Element, target: etree._Element) -> etree._Element | None:
        cur = target
        while cur is not None and cur.getparent() is not None and cur.getparent() is not container:
            cur = cur.getparent()
        if cur is not None and cur.getparent() is container:
            return cur
        return None

    def _text_or_body_container(elem: etree._Element) -> etree._Element | None:
        preferred: etree._Element | None = None
        fallback: etree._Element | None = None
        cur: etree._Element | None = elem
        while cur is not None:
            lt = _local_tag(cur).casefold()
            if lt == "text":
                preferred = cur
                break
            if lt == "body" and fallback is None:
                fallback = cur
            cur = cur.getparent()
        return preferred or fallback

    if include_from_start:
        container = _text_or_body_container(end_elem) or _lowest_common_ancestor(start_elem, end_elem)
    else:
        container = _lowest_common_ancestor(start_elem, end_elem)

    if container is None:
        return "".join(etree.tostring(e, encoding="unicode") for e in aligned[start_idx : end_idx + 1])

    children = list(container)
    if not children:
        return etree.tostring(container, encoding="unicode")

    end_top = _first_top_child_under(container, end_elem)
    if end_top is None:
        return "".join(etree.tostring(e, encoding="unicode") for e in aligned[start_idx : end_idx + 1])

    if include_from_start:
        i = 0
    else:
        start_top = _first_top_child_under(container, start_elem)
        if start_top is None:
            return "".join(etree.tostring(e, encoding="unicode") for e in aligned[start_idx : end_idx + 1])
        i = children.index(start_top)

    j = children.index(end_top)
    if j < i:
        i, j = j, i
    return "".join(etree.tostring(k, encoding="unicode") for k in children[i : j + 1])


def resolve_fragment_source_paths(set_id: str, doc_key: str, project_root: Path) -> tuple[list[Path], str | None]:
    """Resolve API ``doc`` parameter to one or more XML paths.

    If the manifest row has a ``witness`` id, **all** manifest rows with the same
    witness are concatenated in manifest order (multi-file logical witness).
    Otherwise the single matched path is used.

    ``set_id`` may be ``__direct__`` (pair editor / tuview): resolve ``doc_key`` as a path
    under ``project_root`` only — no alignment-set manifest.
    """
    doc_key = doc_key.strip()
    root = project_root.resolve()
    sid = (set_id or "").strip()
    if sid == "__direct__":
        try:
            p = Path(doc_key).expanduser()
            if not p.is_absolute():
                p = (root / p).resolve()
            else:
                p = p.resolve()
        except OSError as exc:
            raise FileNotFoundError(f"Invalid fragment doc path: {doc_key!r}") from exc
        try:
            p.relative_to(root)
        except ValueError as exc:
            raise FileNotFoundError(
                f"Fragment doc must be under project root {root}: {doc_key!r}"
            ) from exc
        if p.is_file():
            return [p], None
        raise FileNotFoundError(f"Fragment doc not found: {doc_key!r}")

    members = resolve_alignment_set_members_detailed(set_id, project_root)
    target_resolved: Path | None = None
    try:
        target_resolved = Path(doc_key).expanduser().resolve()
    except OSError:
        target_resolved = None

    match: dict[str, Any] | None = None
    for m in members:
        mp = Path(m["path"]).resolve()
        if doc_key == m["path"] or (target_resolved is not None and mp == target_resolved):
            match = m
            break
        rel = (m.get("relative_path") or "").strip()
        if rel and (doc_key == rel or doc_key.endswith(rel)):
            match = m
            break

    if match is None:
        loose = Path(doc_key)
        if loose.is_file():
            return [loose.resolve()], None
        raise FileNotFoundError(f"Document not part of alignment set `{set_id}`: {doc_key}")

    witness = (match.get("witness") or "").strip()
    if witness:
        paths = [Path(m["path"]).resolve() for m in members if (m.get("witness") or "").strip() == witness]
        return paths, witness

    return [Path(match["path"]).resolve()], None


def slice_aligned_units(
    units: list[dict[str, Any]],
    *,
    offset: int,
    limit: int,
    anchor: str,
    context: int,
) -> tuple[list[dict[str, Any]], int, bool, str | None]:
    """Return (items, next_offset, has_more, warn_message).

    If ``anchor`` is set and ``offset == 0``, the window starts at ``anchor`` minus
    ``context`` rows (jump-to). Otherwise ``offset`` is a linear index into the
    aligned-unit list (pagination / load-more).
    """
    n = len(units)
    offset_clamped = max(0, min(offset, n))
    start = offset_clamped
    warn: str | None = None
    if anchor.strip() and offset == 0:
        idx = _find_anchor_index(units, anchor.strip())
        if idx is None:
            return [], 0, False, f"Anchor not found at this level: {anchor!r}"
        start = max(0, idx - max(0, context))

    end = min(n, start + max(1, limit))
    page = units[start:end]
    next_offset = end
    has_more = end < n
    return page, next_offset, has_more, warn


def _find_anchor_index(units: list[dict[str, Any]], anchor: str) -> int | None:
    for i, row in enumerate(units):
        if row.get("tuid") == anchor or row.get("id") == anchor:
            return i
    anchor_cf = anchor.casefold()
    for i, row in enumerate(units):
        tuid = (row.get("tuid") or "").strip()
        uid = (row.get("id") or "").strip()
        if tuid and anchor_cf in tuid.casefold():
            return i
        if uid and anchor_cf in uid.casefold():
            return i
    return None


def build_fragment_payload(
    *,
    set_id: str,
    doc_key: str,
    project_root: Path,
    level: str = "s",
    anchor: str = "",
    offset: int = 0,
    limit: int = 25,
    context: int = 3,
    include_front: bool = False,
) -> dict[str, Any]:
    """Build the JSON object returned by ``flexalign info fragment`` / tuview API."""
    root = project_root.resolve()
    paths, witness = resolve_fragment_source_paths(set_id, doc_key, root)

    units: list[dict[str, Any]] = []
    witness_css_parts: list[str] = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"TEI file not found: {path}")
        tree = _load_tree(path)
        css = extract_embedded_css(tree)
        if css:
            witness_css_parts.append(css)
        src = str(path)
        file_units = iter_aligned_units_for_level(path, level)
        for i, row in enumerate(file_units):
            row["__file_idx"] = i
            row["source_file"] = src
        units.extend(file_units)

    warn_suffix = f" ({len(paths)} files)" if len(paths) > 1 else ""
    if not units:
        return {
            "set": set_id,
            "doc": doc_key,
            "doc_paths": [str(p) for p in paths],
            "witness": witness,
            "level": level,
            "anchor": anchor,
            "context": max(0, context),
            "offset": offset,
            "limit": limit,
            "items": [],
            "has_more": False,
            "next_offset": 0,
            "window_xml": "",
            "witness_css": "\n\n".join(witness_css_parts) or None,
            "placeholder": False,
            "message": f"No aligned units (@tuid) at level {level!r}{warn_suffix}.",
        }

    page, next_offset, has_more, warn = slice_aligned_units(
        units,
        offset=max(0, offset),
        limit=limit,
        anchor=anchor,
        context=max(0, context),
    )

    msg_parts: list[str] = []
    if warn:
        msg_parts.append(warn)
    if len(paths) > 1:
        msg_parts.append(f"Witness spans {len(paths)} XML files (concatenated in manifest order).")

    anchor_start = 0
    if anchor.strip():
        idx = _find_anchor_index(units, anchor.strip())
        if idx is not None:
            anchor_start = max(0, idx - max(0, context))
    elif offset == 0:
        anchor_start = 0
    window_start = 0 if include_front else min(anchor_start, max(0, next_offset))
    loaded = units[window_start:next_offset]
    by_src: dict[str, tuple[int, int]] = {}
    for row in loaded:
        src = str(row.get("source_file") or "")
        if not src:
            continue
        fi = int(row.get("__file_idx") or 0)
        if src not in by_src:
            by_src[src] = (fi, fi)
        else:
            lo, hi = by_src[src]
            by_src[src] = (min(lo, fi), max(hi, fi))
    window_xml_parts: list[str] = []
    for p in paths:
        src = str(p)
        bounds = by_src.get(src)
        if not bounds:
            continue
        lo, hi = bounds
        window_xml_parts.append(
            _serialize_between_aligned_bounds(
                Path(src),
                level,
                lo,
                hi,
                include_from_start=include_front,
            )
        )

    page_public = [{k: v for k, v in row.items() if not str(k).startswith("__")} for row in page]

    return {
        "set": set_id,
        "doc": doc_key,
        "doc_paths": [str(p) for p in paths],
        "witness": witness,
        "level": level,
        "anchor": anchor,
        "context": max(0, context),
        "offset": offset,
        "limit": limit,
        "items": page_public,
        "has_more": has_more,
        "next_offset": next_offset,
        "window_xml": "".join(window_xml_parts),
        "witness_css": "\n\n".join(witness_css_parts) or None,
        "placeholder": False,
        "message": " ".join(msg_parts) if msg_parts else "",
    }


def fragment_payload_to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


# Levels used when scanning @tuid-bearing elements for pairwise alignment hints (wizard UI).
_TAG_TO_LEVEL_FOR_TUID = {"text": "text", "div": "chapter", "p": "p", "s": "s", "tok": "tok"}
_LEVEL_ORDER_TUID = ("text", "chapter", "p", "s", "tok")


def scan_tuid_level_coverage(path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Per logical level: count of elements with non-empty ``@tuid``, and total elements at that level (tag-based)."""
    counts: dict[str, int] = {}
    totals: dict[str, int] = {}
    tree = _load_tree(path)
    for elem in tree.iter():
        lt = _local_tag(elem).lower()
        lev = _TAG_TO_LEVEL_FOR_TUID.get(lt)
        if not lev:
            continue
        totals[lev] = totals.get(lev, 0) + 1
        if (elem.get("tuid") or "").strip():
            counts[lev] = counts.get(lev, 0) + 1
    return counts, totals


def scan_tuid_level_counts(path: Path) -> dict[str, int]:
    """Count elements with non-empty ``@tuid`` per logical alignment level (tag-based)."""
    counts, _totals = scan_tuid_level_coverage(path)
    return counts


def build_doc_tuid_levels_payload(project_root: Path, relative_paths: list[str]) -> dict[str, Any]:
    """Infer ``--level`` / ``--project-from-level`` for two TEI paths from shared @tuid coverage."""
    rel_norm = [p.strip().replace("\\", "/") for p in relative_paths if p.strip()]
    if len(rel_norm) != 2:
        return {
            "paths": rel_norm,
            "error": "Exactly two project-relative XML paths are required.",
            "per_file": {},
            "intersection_levels": [],
            "align_level": None,
            "project_from_level": None,
            "reason": "",
        }
    root = project_root.resolve()
    per_file: dict[str, dict[str, int]] = {}
    for rp in rel_norm:
        full = (root / rp).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            return {
                "paths": rel_norm,
                "error": f"Path escapes project root: {rp}",
                "per_file": {},
                "intersection_levels": [],
                "align_level": None,
                "project_from_level": None,
                "reason": "",
            }
        if not full.is_file():
            return {
                "paths": rel_norm,
                "error": f"File not found: {rp}",
                "per_file": {},
                "intersection_levels": [],
                "align_level": None,
                "project_from_level": None,
                "reason": "",
            }
        per_file[rp] = scan_tuid_level_counts(full)

    intersection: list[str] = []
    for lev in _LEVEL_ORDER_TUID:
        if all(per_file[r].get(lev, 0) > 0 for r in rel_norm):
            intersection.append(lev)

    align_level: str | None = intersection[-1] if intersection else None
    project_from: str | None = None
    reason_parts: list[str] = []
    if align_level == "tok":
        if "s" in intersection:
            project_from = "s"
            reason_parts.append(
                "Finest shared @tuid level is tok; implied step runs segmentation from s, then aligns at tok."
            )
        else:
            reason_parts.append(
                "Finest shared @tuid level is tok with no shared s-level @tuid — align at tok without projection."
            )
    elif align_level:
        reason_parts.append(f"Finest shared @tuid level in both files is {align_level} (align at that level).")
    else:
        reason_parts.append(
            "No overlapping TEI level carries @tuid in both files — add tuids or choose other witnesses."
        )

    return {
        "paths": rel_norm,
        "per_file": per_file,
        "intersection_levels": intersection,
        "align_level": align_level,
        "project_from_level": project_from,
        "reason": " ".join(reason_parts),
    }


def build_set_members_tuid_scan_payload(
    set_id: str,
    *,
    project_root: Path,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Per manifest member: counts of elements with ``@tuid`` by logical level (TEI tag).

    Used by the TEITOK wizard to show which alignment levels are already annotated.
    """
    members = resolve_alignment_set_members_detailed(
        set_id, project_root=project_root, force_refresh=force_refresh
    )
    root = project_root.resolve()
    enriched: list[dict[str, Any]] = []
    for m in members:
        row = dict(m)
        rel = (
            (row.get("relative_path") or row.get("path") or "").strip().replace("\\", "/")
        )
        row["tuid_level_counts"] = {}
        row["tuid_level_totals"] = {}
        row["tuid_scan_error"] = None
        if not rel:
            row["tuid_scan_error"] = "missing relative path"
            enriched.append(row)
            continue
        full = (root / rel).resolve()
        try:
            full.relative_to(root)
        except ValueError:
            row["tuid_scan_error"] = "path outside project root"
            enriched.append(row)
            continue
        if not full.is_file():
            row["tuid_scan_error"] = "file not found"
            enriched.append(row)
            continue
        try:
            counts, totals = scan_tuid_level_coverage(full)
            row["tuid_level_counts"] = counts
            row["tuid_level_totals"] = totals
        except Exception as exc:
            row["tuid_scan_error"] = f"{type(exc).__name__}: {exc}"
        enriched.append(row)
    return {"set": set_id, "members": enriched}
