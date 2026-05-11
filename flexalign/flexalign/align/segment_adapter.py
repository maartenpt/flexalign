"""Map TEI AlignDoc units to format-neutral segment views for backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .align_doc import AlignDoc, AlignUnit


@dataclass
class SegmentView:
    """One alignable unit derived from TEI (or other sources via attrs)."""

    anchor_id: str
    text: str
    tuid: str | None
    attrs: dict[str, str]
    element: Any | None = None  # optional lxml element for backends that walk the DOM (e.g. awesome)


XML_ID_KEY = "{http://www.w3.org/XML/1998/namespace}id"


def segment_attr_for_align(view: SegmentView, attr: str) -> str:
    """Mirror TEI `element.get(attr) or xml:id or unit id` resolution used by AttributeBackend."""
    raw = view.attrs.get(attr) or view.attrs.get(XML_ID_KEY) or view.anchor_id
    return (raw or "").strip()


def _element_attribs(elem: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if elem is None:
        return out
    try:
        for k, v in elem.attrib.items():
            out[str(k)] = "" if v is None else str(v)
    except Exception:
        pass
    return out


def segment_views_from_align_doc(doc: AlignDoc, level: str) -> list[SegmentView]:
    """Build segment views from a loaded TEI document."""
    views: list[SegmentView] = []
    for unit in doc.iter_units(level):
        if not unit.unit_id:
            continue
        views.append(
            SegmentView(
                anchor_id=unit.unit_id,
                text=unit.text,
                tuid=unit.element.get("tuid") if unit.element is not None else None,
                attrs=_element_attribs(unit.element),
                element=unit.element,
            )
        )
    return views


def align_units_to_segment_views(units: list[AlignUnit]) -> list[SegmentView]:
    """Convert pre-fetched AlignUnit list to segment views."""
    views: list[SegmentView] = []
    for unit in units:
        if not unit.unit_id:
            continue
        views.append(
            SegmentView(
                anchor_id=unit.unit_id,
                text=unit.text,
                tuid=unit.element.get("tuid") if unit.element is not None else None,
                attrs=_element_attribs(unit.element),
                element=unit.element,
            )
        )
    return views
