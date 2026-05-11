"""Moses-style plain parallel corpus import/export."""

from __future__ import annotations

from pathlib import Path

from ..align.ir import AlignmentDocument, AlignmentGroup, PairRow, ParentBlock


def _read_lines(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return text.splitlines()


def load_alignment_from_moses(
    src_path: str | Path,
    tgt_path: str | Path,
    *,
    version1: str | None = None,
    version2: str | None = None,
    ids_path: str | Path | None = None,
    level: str = "s",
) -> AlignmentDocument:
    """
    Load sentence-aligned plain text (one segment per line, UTF-8).

    If ``ids_path`` is given, each line is a shared anchor id used for both sides
    (suitable for TEI writeback when ids match ``xml:id``).
    """
    src_path = Path(src_path)
    tgt_path = Path(tgt_path)
    v1 = version1 or str(src_path).replace("\\", "/")
    v2 = version2 or str(tgt_path).replace("\\", "/")
    src_lines = _read_lines(src_path)
    tgt_lines = _read_lines(tgt_path)
    n = min(len(src_lines), len(tgt_lines))
    ids: list[str] | None = None
    if ids_path is not None:
        ids = [ln.strip() for ln in _read_lines(Path(ids_path))]
        n = min(n, len(ids))
    rows: list[PairRow] = []
    for i in range(n):
        text1 = src_lines[i]
        text2 = tgt_lines[i]
        if ids is not None and ids[i]:
            anchor = ids[i]
            id1 = [anchor]
            id2 = [anchor]
        else:
            anchor = f"L{i + 1}"
            id1 = [anchor]
            id2 = [anchor]
        rows.append(
            PairRow(
                id1=id1,
                id2=id2,
                text1=text1,
                text2=text2,
                score=1.0,
                edit="auto",
                tuid_at_write_1=None,
                tuid_at_write_2=None,
            )
        )
    return AlignmentDocument(
        version1=v1,
        version2=v2,
        level=level,
        parent_level=None,
        pivot="version1",
        method="moses",
        mode="direct",
        alignments=[AlignmentGroup(parent=ParentBlock(id1=[], id2=[]), pairs=rows)],
        method_detail="moses-parallel",
        notes=[],
        meta_extra={"moses_src": str(src_path), "moses_tgt": str(tgt_path)},
    )


def write_alignment_to_moses(
    doc: AlignmentDocument,
    src_path: str | Path,
    tgt_path: str | Path,
    *,
    ids_path: str | Path | None = None,
) -> None:
    """Write one line per pair row (M:N joins text with spaces)."""
    src_path = Path(src_path)
    tgt_path = Path(tgt_path)
    src_lines: list[str] = []
    tgt_lines: list[str] = []
    id_lines: list[str] = []
    for group in doc.alignments:
        for row in group.pairs:
            src_lines.append(" ".join((row.text1 or "").split()) if row.text1 else "")
            tgt_lines.append(" ".join((row.text2 or "").split()) if row.text2 else "")
            if ids_path is not None:
                joined = "|".join(row.id1) if row.id1 else ""
                if not joined and row.id2:
                    joined = "|".join(row.id2)
                id_lines.append(joined)
    src_path.write_text("\n".join(src_lines) + ("\n" if src_lines else ""), encoding="utf-8")
    tgt_path.write_text("\n".join(tgt_lines) + ("\n" if tgt_lines else ""), encoding="utf-8")
    if ids_path is not None:
        Path(ids_path).write_text("\n".join(id_lines) + ("\n" if id_lines else ""), encoding="utf-8")
