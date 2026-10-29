"""Bitexts: alignments between two documents as beads over their unit ids (XCES, pair JSON, TMX, Moses)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

# a unit: (document, unit id), e.g. ("en/ep-00-01-17.xml", "s12")
Unit = Tuple[str, str]


@dataclass(frozen=True)
class Bead:
    """Units of document A aligned with units of document B; one side empty = unaligned (1:0, 0:1)."""

    __slots__ = ("a", "b")   # millions of them in a large corpus
    a: Tuple[str, ...]
    b: Tuple[str, ...]


@dataclass
class Bitext:
    """One alignment between two documents (a sentence-level XCES linkGrp, a pair JSON, …)."""

    doc_a: str
    doc_b: str
    beads: List[Bead] = field(default_factory=list)
    source: str = ""   # where it came from, for reports
