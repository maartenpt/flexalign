"""Push parent-level tuids down to a lower level."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from lxml import etree

from .tuid import join_tuids, parse_tuid

LEVEL_TAG = {
    "text": "text",
    "chapter": "div",
    "p": "p",
    "s": "s",
    "tok": "tok",
}


@dataclass
class PushdownStats:
    parents_seen: int = 0
    children_seen: int = 0
    children_written: int = 0
    children_skipped_existing: int = 0


def _level_xpath(level: str) -> str:
    tag = LEVEL_TAG.get(level, level)
    return f".//*[local-name()='{tag}']"


def _child_index(node: etree._Element, *, idx: int, index_source: str) -> int:
    if index_source == "ord":
        ord_value = (node.get("ord") or "").strip()
        if ord_value.isdigit():
            return int(ord_value)
    return idx + 1


def pushdown_tuids_in_tree(
    root: etree._Element,
    *,
    from_level: str,
    to_level: str,
    template: str,
    overwrite: bool,
    index_source: str,
) -> PushdownStats:
    stats = PushdownStats()
    next_index_by_parent: dict[str, int] = {}
    for parent in root.xpath(f"{_level_xpath(from_level)}[@tuid]"):
        parent_tuids = parse_tuid(parent.get("tuid"))
        if not parent_tuids:
            continue
        stats.parents_seen += 1
        children = parent.xpath(_level_xpath(to_level))
        for idx, child in enumerate(children):
            stats.children_seen += 1
            if child.get("tuid") and not overwrite:
                stats.children_skipped_existing += 1
                continue
            child_number = _child_index(child, idx=idx, index_source=index_source)
            minted: list[str] = []
            for parent_tuid in parent_tuids:
                if parent_tuid not in next_index_by_parent:
                    next_index_by_parent[parent_tuid] = child_number
                number = next_index_by_parent[parent_tuid]
                minted_piece = template.format(parent=parent_tuid, index=number, ord=child_number)
                minted.append(minted_piece)
                # Continue counters across repeated parent-tuids in later sentences.
                match = re.search(r"(\d+)(?!.*\d)", minted_piece)
                if match:
                    next_index_by_parent[parent_tuid] = int(match.group(1)) + 1
                else:
                    next_index_by_parent[parent_tuid] = number + 1
            child.set("tuid", join_tuids(minted))
            stats.children_written += 1
    return stats


def pushdown_file(
    *,
    input_path: Path,
    output_path: Path,
    from_level: str,
    to_level: str,
    template: str,
    overwrite: bool,
    index_source: str,
) -> PushdownStats:
    tree = etree.parse(str(input_path), parser=etree.XMLParser(remove_blank_text=False, recover=True))
    stats = pushdown_tuids_in_tree(
        tree.getroot(),
        from_level=from_level,
        to_level=to_level,
        template=template,
        overwrite=overwrite,
        index_source=index_source,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(etree.tostring(tree, encoding="utf-8", xml_declaration=True, pretty_print=True))
    return stats

