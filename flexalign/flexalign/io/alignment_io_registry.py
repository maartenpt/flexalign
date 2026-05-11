"""Registry for alignment document loaders/savers (convert command)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..align.ir import AlignmentDocument
from .jsonio import load_json
from .moses import load_alignment_from_moses, write_alignment_to_moses
from .teitok_export import write_alignment_to_teitok_xml
from .tmx import load_alignment_from_tmx, write_alignment_to_tmx


AlignmentLoader = Callable[..., AlignmentDocument]
AlignmentSaver = Callable[..., None]


@dataclass
class AlignmentInputEntry:
    name: str
    aliases: tuple[str, ...]
    loader: AlignmentLoader

    def matches(self, value: str) -> bool:
        n = value.lower()
        return n == self.name.lower() or n in (a.lower() for a in self.aliases)


@dataclass
class AlignmentOutputEntry:
    name: str
    aliases: tuple[str, ...]
    saver: AlignmentSaver

    def matches(self, value: str) -> bool:
        n = value.lower()
        return n == self.name.lower() or n in (a.lower() for a in self.aliases)


class AlignmentIORegistry:
    def __init__(self) -> None:
        self._inputs: Dict[str, AlignmentInputEntry] = {}
        self._outputs: Dict[str, AlignmentOutputEntry] = {}

    def register_input(self, entry: AlignmentInputEntry) -> None:
        self._inputs[entry.name.lower()] = entry
        for a in entry.aliases:
            self._inputs[a.lower()] = entry

    def register_output(self, entry: AlignmentOutputEntry) -> None:
        self._outputs[entry.name.lower()] = entry
        for a in entry.aliases:
            self._outputs[a.lower()] = entry

    def get_input(self, name: str) -> Optional[AlignmentInputEntry]:
        return self._inputs.get(name.lower()) if name else None

    def get_output(self, name: str) -> Optional[AlignmentOutputEntry]:
        return self._outputs.get(name.lower()) if name else None


alignment_registry = AlignmentIORegistry()


def _load_pair(path: Path, *, level: str = "s", **_: Any) -> AlignmentDocument:
    return AlignmentDocument.from_pair_payload(load_json(path))


def _load_reconcile(path: Path, *, version1: str, version2: str, level: str = "s", **_: Any) -> AlignmentDocument:
    return AlignmentDocument.from_reconcile_payload(load_json(path), version1=version1, version2=version2)


def _load_tmx(
    path: Path,
    *,
    level: str = "s",
    version1: str | None = None,
    version2: str | None = None,
    lang_src: str | None = None,
    lang_tgt: str | None = None,
    **_: Any,
) -> AlignmentDocument:
    return load_alignment_from_tmx(
        path,
        version1=version1,
        version2=version2,
        lang_src=lang_src,
        lang_tgt=lang_tgt,
        level=level,
    )


def _load_moses(
    path: Path,
    *,
    moses_secondary: Path,
    level: str = "s",
    version1: str | None = None,
    version2: str | None = None,
    ids_path: Path | None = None,
    **_: Any,
) -> AlignmentDocument:
    return load_alignment_from_moses(
        path,
        moses_secondary,
        version1=version1,
        version2=version2,
        ids_path=ids_path,
        level=level,
    )


def _save_pair(doc: AlignmentDocument, path: Path, **_: Any) -> None:
    import json

    Path(path).write_text(json.dumps(doc.to_pair_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


def _save_reconcile(doc: AlignmentDocument, path: Path, *, level: str | None = None, **_: Any) -> None:
    import json

    payload = doc.to_reconcile_payload(level=level)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_tmx(
    doc: AlignmentDocument,
    path: Path,
    *,
    lang_src: str,
    lang_tgt: str,
    tuid_max_length: int | None = None,
    tuid_prefix: str | None = None,
    **_: Any,
) -> None:
    write_alignment_to_tmx(
        doc,
        path,
        lang_src=lang_src,
        lang_tgt=lang_tgt,
        tuid_max_length=tuid_max_length,
        tuid_prefix=tuid_prefix,
    )


def _save_teitok(
    doc: AlignmentDocument,
    path: Path,
    *,
    lang_src: str,
    lang_tgt: str,
    tuid_max_length: int | None = None,
    tuid_prefix: str | None = None,
    **_: Any,
) -> None:
    p = Path(path)
    write_alignment_to_teitok_xml(
        doc,
        p,
        lang_src=str(lang_src or "und"),
        lang_tgt=str(lang_tgt or "und"),
        title=p.stem,
        tuid_max_length=tuid_max_length,
        tuid_prefix=tuid_prefix,
    )


def _save_moses(
    doc: AlignmentDocument,
    path: Path,
    *,
    moses_tgt: Path,
    ids_path: Path | None = None,
    **_: Any,
) -> None:
    write_alignment_to_moses(doc, path, moses_tgt, ids_path=ids_path)


def register_default_alignment_formats() -> None:
    if alignment_registry.get_input("pair"):
        return
    alignment_registry.register_input(AlignmentInputEntry("pair", ("pair-json", "json"), _load_pair))
    alignment_registry.register_input(AlignmentInputEntry("reconcile", ("reconcile-json",), _load_reconcile))
    alignment_registry.register_input(AlignmentInputEntry("tmx", (), _load_tmx))
    alignment_registry.register_input(AlignmentInputEntry("moses", ("moses-parallel",), _load_moses))
    alignment_registry.register_output(AlignmentOutputEntry("pair", ("pair-json", "json"), _save_pair))
    alignment_registry.register_output(AlignmentOutputEntry("reconcile", ("reconcile-json",), _save_reconcile))
    alignment_registry.register_output(AlignmentOutputEntry("tmx", (), _save_tmx))
    alignment_registry.register_output(
        AlignmentOutputEntry("teitok", ("tei", "tei-new", "tei-parallel"), _save_teitok),
    )
    alignment_registry.register_output(AlignmentOutputEntry("moses", ("moses-parallel",), _save_moses))


register_default_alignment_formats()
