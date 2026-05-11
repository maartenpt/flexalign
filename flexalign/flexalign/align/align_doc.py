"""AlignDoc wrapper for TEI files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree


@dataclass
class AlignUnit:
    level: str
    unit_id: str
    text: str
    element: etree._Element


class AlignDoc:
    def __init__(self, tree: etree._ElementTree, path: Path) -> None:
        self.tree = tree
        self.path = path
        self.root = tree.getroot()

    @classmethod
    def from_file(cls, path: str | Path) -> "AlignDoc":
        source = Path(path)
        parser = etree.XMLParser(remove_blank_text=False, recover=True)
        tree = etree.parse(str(source), parser)
        return cls(tree, source)

    def iter_units(self, level: str) -> list[AlignUnit]:
        tag = {
            "text": "text",
            "chapter": "div",
            "p": "p",
            "s": "s",
            "tok": "tok",
        }.get(level, level)
        units: list[AlignUnit] = []
        for elem in self.root.xpath(f".//*[local-name()='{tag}']"):
            unit_id = (
                elem.get("{http://www.w3.org/XML/1998/namespace}id")
                or elem.get("id")
                or elem.get("tuid")
                or ""
            )
            text = " ".join(part for part in elem.itertext()).strip()
            units.append(AlignUnit(level=level, unit_id=unit_id, text=text, element=elem))
        return units

    def get_unit_by_id(self, unit_id: str) -> etree._Element | None:
        query = (
            ".//*[@xml:id=$id or @id=$id]",
        )
        result = self.root.xpath(query[0], id=unit_id, namespaces={"xml": "http://www.w3.org/XML/1998/namespace"})
        return result[0] if result else None

