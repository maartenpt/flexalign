"""Main flexalign CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .align.aer import compute_aer_from_files
from .align.apply import apply_from_path, apply_tok_refs_from_path
from .align.cascade import run_cascade
from .align.projection import segment_from_pivot
from .align.pushdown import pushdown_file
from .align.reconcile import reconcile_files
from .io.alignment_sets import resolve_alignment_set_plan
from .io.jsonio import migrate_histalign_file

# Order for --project-from-level through --level (see align subcommand help).
_PROJECTION_LEVELS = ("s", "tok")


def _projection_chain(project_from: str, align_level: str) -> list[str]:
    try:
        start = _PROJECTION_LEVELS.index(project_from)
        end = _PROJECTION_LEVELS.index(align_level)
    except ValueError as exc:
        raise ValueError(
            f"--project-from-level and --level must each be one of: {', '.join(_PROJECTION_LEVELS)}"
        ) from exc
    if start > end:
        raise ValueError(
            f"--project-from-level ({project_from}) must be at or above --level ({align_level}) "
            f"in projection order {list(_PROJECTION_LEVELS)}"
        )
    return list(_PROJECTION_LEVELS[start : end + 1])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flexalign", allow_abbrev=False)
    subparsers = parser.add_subparsers(dest="task")

    align = subparsers.add_parser("align")
    align.add_argument("--backend", default="identity")
    align.add_argument("--level", default="s")
    align.add_argument("--pivot", nargs=2)
    align.add_argument("--set", dest="set_id")
    align.add_argument("--pivot-mode", choices=["first", "all"], default="first")
    align.add_argument("--project-root")
    align.add_argument("--output", required=True)
    align.add_argument("--attr", default="xml:id")
    align.add_argument(
        "--project-from-level",
        choices=list(_PROJECTION_LEVELS),
        default=None,
        help=(
            "Before aligning, run segmentation projection from pivot to target for each level "
            f"from this flag through --level (order: {' → '.join(_PROJECTION_LEVELS)}). "
            "Requires --level to be one of that ordered pair."
        ),
    )

    set_cmd = subparsers.add_parser("set")
    set_cmd.add_argument(
        "set_action",
        choices=("create", "add-doc", "remove-doc", "set-pivot", "update-doc"),
        help="create manifest | add or remove member | update metadata | mark pivot document",
    )
    set_cmd.add_argument("--id", help="Alignment set id (create)")
    set_cmd.add_argument(
        "--title",
        default="",
        help="Set title (create) or member title attribute (add-doc)",
    )
    set_cmd.add_argument("--set", dest="set_id", help="Alignment set id (add-doc, remove-doc, set-pivot)")
    set_cmd.add_argument("--path", help="Document path under project (add-doc, remove-doc, set-pivot)")
    set_cmd.add_argument("--member-id", default=None, help="Member id attribute (add-doc)")
    set_cmd.add_argument("--witness", default=None, help="Witness label (add-doc)")
    set_cmd.add_argument(
        "--pivot",
        action="store_true",
        help="Set pivot=true on this member (add-doc)",
    )
    set_cmd.add_argument(
        "--keep-others",
        action="store_true",
        help="With set-pivot: do not remove pivot from other members",
    )
    set_cmd.add_argument("--project-root")
    set_cmd.add_argument(
        "--member-witness",
        dest="member_witness_update",
        default=argparse.SUPPRESS,
        help="update-doc: manifest witness label (empty removes)",
    )
    set_cmd.add_argument(
        "--member-title",
        dest="member_title_update",
        default=argparse.SUPPRESS,
        help="update-doc: manifest title (empty removes)",
    )

    cascade = subparsers.add_parser("cascade")
    cascade.add_argument("--pivot", nargs=2)
    cascade.add_argument("--set", dest="set_id")
    cascade.add_argument("--pivot-mode", choices=["first", "all"], default="first")
    cascade.add_argument("--project-root")
    cascade.add_argument("--steps", default="text,chapter,p,s")
    cascade.add_argument("--backends", default="")
    cascade.add_argument("--out-dir", default="Alignments/Pairs")
    cascade.add_argument("--segment-from-pivot", default=None)

    rec = subparsers.add_parser("reconcile")
    rec.add_argument("--level", required=True)
    rec.add_argument("pair_files", nargs="+")
    rec.add_argument("--output", required=True)
    rec.add_argument("--ignore-tuid-drift", action="store_true")

    conv = subparsers.add_parser(
        "convert",
        help="Convert alignment between pair JSON, reconcile JSON, TMX, Moses parallel text, and TEI TUID writeback.",
    )
    conv.add_argument("--from", dest="from_fmt", required=True, help="Source format: pair, reconcile, tmx, moses")
    conv.add_argument(
        "--to",
        dest="to_fmt",
        required=True,
        help="Target format: pair, reconcile, tmx, moses, teitok (new TEI/XML), tei-writeback (apply tuids to existing XML)",
    )
    conv.add_argument(
        "--input",
        required=True,
        help="Primary input file (pair/reconcile JSON, TMX, or Moses source side)",
    )
    conv.add_argument(
        "--output",
        required=True,
        help="Output path (format-specific). For teitok/tei: new TEI file. For tei-writeback: still required; pivot/target XML paths come from the document.",
    )
    conv.add_argument(
        "--moses-secondary",
        default=None,
        help="Moses target corpus path (required for from/to moses: parallel other-language file)",
    )
    conv.add_argument(
        "--version1",
        default=None,
        help="Document path for pivot side (reconcile import: must match keys in reconcile JSON members)",
    )
    conv.add_argument(
        "--version2",
        default=None,
        help="Document path for target side (reconcile import: must match keys in reconcile JSON members)",
    )
    conv.add_argument("--level", default="s", help="Alignment level metadata (default: s)")
    conv.add_argument(
        "--lang-src",
        default=None,
        help="TMX/teitok: source xml:lang (optional; from TMX <tu srclang> / first tuv when omitted)",
    )
    conv.add_argument(
        "--lang-tgt",
        default=None,
        help="TMX/teitok: target xml:lang (optional; from second tuv / non-srclang side when omitted)",
    )
    conv.add_argument("--ids-path", default=None, help="Moses import: optional one-id-per-line sidecar shared by both sides")
    conv.add_argument("--moses-ids-out", default=None, help="Moses export: optional path to write anchor ids (pipe-separated if many)")
    conv.add_argument("--pivot", default=None, help="tei-writeback: pivot TEI/XML path (propagates tuids onto version2 in the pair document)")
    conv.add_argument(
        "--project-root",
        default=None,
        help="tei-writeback / pair paths: project root for resolving relative paths in the alignment document",
    )
    conv.add_argument("--out-dir", default=None, help="tei-writeback: write modified XML under this directory")
    conv.add_argument("--ignore-tuid-drift", action="store_true", help="tei-writeback: do not abort on tuid drift")
    conv.add_argument("--invalidate-below", action="store_true", help="tei-writeback: strip orphan tuids")
    conv.add_argument("--mark-needs-review", action="store_true", help="tei-writeback: mark unexpected tuids for review")
    conv.add_argument(
        "--tuid-max-length",
        type=int,
        default=0,
        metavar="N",
        help=(
            "When writing TMX/teitok (no --tuid-prefix): shorten fragments longer than N chars to t+hex. "
            "0 = keep verbatim source tuids (default). Ignored when --tuid-prefix is set."
        ),
    )
    conv.add_argument(
        "--tuid-prefix",
        default=None,
        metavar="PREFIX",
        help=(
            "When writing TMX/teitok: emit tuids as PREFIX-s1, PREFIX-s2, … (PREFIX-w1, … at --level tok). "
            "PREFIX is sanitized for XML; supply a corpus or set id (e.g. vec.common-voice-conv)."
        ),
    )
    conv.add_argument(
        "--compact-tuids",
        action="store_true",
        help=(
            "After load, rewrite all tuid_at_write_* in the IR: with --tuid-prefix, same ordinal scheme as export; "
            "otherwise use --tuid-max-length, defaulting to 56 for hash compaction when max is 0."
        ),
    )

    plain = subparsers.add_parser(
        "plain",
        help="Plain-text witnesses: segment to minimal TEI, align, then use convert for TMX/Moses/etc.",
    )
    plain_sub = plain.add_subparsers(dest="plain_action", required=True)
    pprep = plain_sub.add_parser(
        "prepare",
        help="Convert each matching .txt under a directory to minimal TEI (s or tok) for use with flexalign align.",
    )
    pprep.add_argument("--input-dir", required=True, type=Path, help="Directory containing plain text files")
    pprep.add_argument("--out-dir", required=True, type=Path, help="Directory to write *.tei.xml files into")
    pprep.add_argument(
        "--glob",
        dest="file_glob",
        default="*.txt",
        help="Glob pattern relative to input-dir (default: *.txt)",
    )
    pprep.add_argument(
        "--recursive",
        action="store_true",
        help="Use recursive glob (rglob) from input-dir",
    )
    pprep.add_argument("--level", choices=("s", "tok"), default="s", help="Structural level to emit (default: s)")
    pprep.add_argument(
        "--segmenter",
        choices=("builtin", "flexipipe"),
        default="builtin",
        help="builtin: simple rules; flexipipe: flexipipe.doc.Document.from_plain_text (requires flexipipe installed)",
    )
    pprep.add_argument("--lang", default=None, help="BCP47 language for xml:lang on <text> (optional)")
    pprep.add_argument(
        "--lang-detect",
        action="store_true",
        help="Guess language per file with langdetect when --lang is not set (optional dependency)",
    )
    pprep.add_argument("--manifest", default=None, type=Path, help="Write a JSON manifest of generated witnesses")

    pap = plain_sub.add_parser(
        "align-pair",
        help="Align two .txt or TEI paths: wrap plain text to TEI in --work-dir, run align, write pair JSON; optional TMX/Moses export.",
    )
    pap.add_argument("pivot", type=Path, help="Pivot plain .txt or TEI/XML path")
    pap.add_argument("target", type=Path, help="Target plain .txt or TEI/XML path")
    pap.add_argument("--output", required=True, type=Path, help="Output pair JSON path")
    pap.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for generated TEI when inputs are .txt (default: .flexalign_plain_work under cwd)",
    )
    pap.add_argument("--backend", default="identity")
    pap.add_argument("--level", choices=("s", "tok"), default="s")
    pap.add_argument("--attr", default="xml:id")
    pap.add_argument("--segmenter", choices=("builtin", "flexipipe"), default="builtin")
    pap.add_argument("--lang", default=None, help="Optional xml:lang when wrapping plain .txt files")
    pap.add_argument("--lang-detect", action="store_true", help="Guess language when wrapping .txt (langdetect)")
    pap.add_argument("--export-tmx", type=Path, default=None, help="Also write this TMX path after alignment")
    pap.add_argument("--tmx-lang-src", default=None, help="TMX source xml:lang (default: en)")
    pap.add_argument("--tmx-lang-tgt", default=None, help="TMX target xml:lang (default: und)")
    pap.add_argument("--export-moses-src", type=Path, default=None, help="Moses-style source lines output")
    pap.add_argument("--export-moses-tgt", type=Path, default=None, help="Moses-style target lines output")
    pap.add_argument("--export-moses-ids", type=Path, default=None, help="Optional Moses id sidecar when exporting")

    app = subparsers.add_parser("apply")
    app.add_argument("path")
    app.add_argument("--pivot")
    app.add_argument(
        "--project-root",
        default=None,
        help="Resolve relative version1/version2 paths in the pair JSON against this directory (TEITOK project root).",
    )
    app.add_argument("--out-dir")
    app.add_argument("--ignore-tuid-drift", action="store_true")
    app.add_argument("--invalidate-below", action="store_true")
    app.add_argument("--mark-needs-review", action="store_true")

    app_tok = subparsers.add_parser(
        "apply-tok-refs",
        help="Write pivot token xml:id values onto target @tok from pair JSON id1→id2 rows (does not modify @tuid).",
    )
    app_tok.add_argument("path", help="Pair JSON path")
    app_tok.add_argument(
        "--project-root",
        default=None,
        help="Resolve relative version2 path in the pair JSON against this directory (TEITOK project root).",
    )
    app_tok.add_argument("--out-dir", default=None, help="Optional output directory for the modified target XML")
    app_tok.add_argument(
        "--attr",
        default="tok",
        help="Target attribute name to store pivot ids (default: tok)",
    )
    app_tok.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing @tok (or --attr) from all <tok> elements in the target before applying",
    )

    aer = subparsers.add_parser("aer")
    aer.add_argument("gold")
    aer.add_argument("auto")

    seg = subparsers.add_parser("segment-from-pivot")
    seg.add_argument("--level", required=True)
    seg.add_argument("--pivot", required=True)
    seg.add_argument("--target", required=True)
    seg.add_argument("--output")

    pushdown = subparsers.add_parser("pushdown")
    pushdown.add_argument("--input", required=True, help="Input XML file")
    pushdown.add_argument("--output", required=True, help="Output XML file")
    pushdown.add_argument("--from-level", required=True, help="Source level carrying parent tuids (e.g. s)")
    pushdown.add_argument("--to-level", required=True, help="Child level to annotate (e.g. tok)")
    pushdown.add_argument(
        "--template",
        default="{parent}:w{index}",
        help="Child tuid format. Placeholders: {parent}, {index}, {ord}.",
    )
    pushdown.add_argument(
        "--index-source",
        choices=["ord", "index"],
        default="ord",
        help="Use child @ord when available, otherwise sequential index.",
    )
    pushdown.add_argument("--overwrite", action="store_true")

    mig = subparsers.add_parser("migrate-histalign")
    mig.add_argument("inputs", nargs="+")
    mig.add_argument("--out", required=True)

    info = subparsers.add_parser("info")
    info.add_argument("info_action", nargs="?", default="backends")
    info.add_argument("--output-format", default="table", choices=["table", "json"])
    info.add_argument("--set", dest="set_id")
    info.add_argument("--project-root")
    info.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force refresh of cached virtual set expansion.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    project_root = Path(args.project_root).resolve() if getattr(args, "project_root", None) else Path.cwd()

    def resolve_pairs() -> list[tuple[str, str]]:
        if getattr(args, "pivot", None):
            return [(args.pivot[0], args.pivot[1])]
        set_id = getattr(args, "set_id", None)
        if set_id:
            plan = resolve_alignment_set_plan(
                set_id,
                project_root=project_root,
                pivot_mode=getattr(args, "pivot_mode", "first"),
            )
            return plan.get("pairs", [])
        raise ValueError("Provide either --pivot A B or --set <alignmentsetuid>")

    if args.task == "align":
        pairs = resolve_pairs()
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        proj_from = getattr(args, "project_from_level", None)
        if proj_from is not None:
            if args.level not in _PROJECTION_LEVELS:
                raise ValueError(
                    f"--project-from-level requires --level to be one of {list(_PROJECTION_LEVELS)}; got {args.level!r}"
                )
            projection_levels = _projection_chain(proj_from, args.level)
        else:
            projection_levels = []
        for index, (pivot_path, target_path) in enumerate(pairs):
            for pl in projection_levels:
                segment_from_pivot(pl, pivot_path, target_path, None)
            payload = run_cascade.align_single(
                backend=args.backend,
                level=args.level,
                pivot_path=pivot_path,
                target_path=target_path,
                attr=args.attr,
            )
            if len(pairs) == 1:
                destination = output_path
            else:
                destination = output_path.with_name(
                    f"{output_path.stem}_{Path(pivot_path).stem}_{Path(target_path).stem}{output_path.suffix or '.json'}"
                )
            destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    if args.task == "cascade":
        for pivot_path, target_path in resolve_pairs():
            run_cascade(
                pivot_path=pivot_path,
                target_path=target_path,
                steps=args.steps.split(","),
                out_dir=Path(args.out_dir),
                backends=args.backends,
                segment_level=args.segment_from_pivot,
            )
        return 0
    if args.task == "reconcile":
        payload = reconcile_files(args.pair_files, args.level, ignore_tuid_drift=args.ignore_tuid_drift)
        Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    if args.task == "convert":
        from .io.convert_runner import run_convert

        run_convert(
            from_fmt=args.from_fmt,
            to_fmt=args.to_fmt,
            input_path=Path(args.input),
            output_path=Path(args.output),
            moses_secondary=Path(args.moses_secondary) if getattr(args, "moses_secondary", None) else None,
            version1=getattr(args, "version1", None),
            version2=getattr(args, "version2", None),
            lang_src=getattr(args, "lang_src", None),
            lang_tgt=getattr(args, "lang_tgt", None),
            level=getattr(args, "level", "s") or "s",
            ids_path=getattr(args, "ids_path", None),
            pivot_path=getattr(args, "pivot", None),
            project_root=getattr(args, "project_root", None),
            out_dir=getattr(args, "out_dir", None),
            ignore_tuid_drift=bool(getattr(args, "ignore_tuid_drift", False)),
            invalidate_below=bool(getattr(args, "invalidate_below", False)),
            mark_needs_review=bool(getattr(args, "mark_needs_review", False)),
            moses_ids_out=getattr(args, "moses_ids_out", None),
            tuid_max_length=int(getattr(args, "tuid_max_length", 0) or 0),
            compact_tuids=bool(getattr(args, "compact_tuids", False)),
            tuid_prefix=getattr(args, "tuid_prefix", None),
        )
        return 0
    if args.task == "plain":
        from .io import plain_pipeline as plain_pipeline_mod

        if args.plain_action == "prepare":
            manifest = plain_pipeline_mod.prepare_directory(
                Path(args.input_dir),
                Path(args.out_dir),
                glob_pattern=str(args.file_glob),
                recursive=bool(args.recursive),
                level=str(args.level),
                segmenter=str(args.segmenter),
                default_lang=getattr(args, "lang", None),
                detect_lang=bool(args.lang_detect),
                manifest_path=Path(args.manifest) if getattr(args, "manifest", None) else None,
            )
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.plain_action == "align-pair":
            work = args.work_dir
            if work is None:
                work = Path.cwd() / ".flexalign_plain_work"
            summary = plain_pipeline_mod.align_plain_or_tei_pair(
                Path(args.pivot),
                Path(args.target),
                Path(args.output),
                work_dir=work,
                backend=str(args.backend),
                level=str(args.level),
                attr=str(args.attr),
                segmenter=str(args.segmenter),
                lang=getattr(args, "lang", None),
                detect_lang=bool(args.lang_detect),
                export_tmx=Path(args.export_tmx) if getattr(args, "export_tmx", None) else None,
                export_tmx_lang_src=getattr(args, "tmx_lang_src", None),
                export_tmx_lang_tgt=getattr(args, "tmx_lang_tgt", None),
                export_moses_src=Path(args.export_moses_src) if getattr(args, "export_moses_src", None) else None,
                export_moses_tgt=Path(args.export_moses_tgt) if getattr(args, "export_moses_tgt", None) else None,
                export_moses_ids=Path(args.export_moses_ids) if getattr(args, "export_moses_ids", None) else None,
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        raise ValueError(f"Unknown plain action: {args.plain_action!r}")
    if args.task == "apply":
        pr_apply = Path(args.project_root).resolve() if getattr(args, "project_root", None) else None
        apply_from_path(
            path=Path(args.path),
            pivot_path=Path(args.pivot) if args.pivot else None,
            out_dir=Path(args.out_dir) if args.out_dir else None,
            project_root=pr_apply,
            ignore_tuid_drift=args.ignore_tuid_drift,
            invalidate_below=args.invalidate_below,
            mark_needs_review=args.mark_needs_review,
        )
        return 0
    if args.task == "apply-tok-refs":
        pr_tok = Path(args.project_root).resolve() if getattr(args, "project_root", None) else None
        slots, writes = apply_tok_refs_from_path(
            path=Path(args.path),
            project_root=pr_tok,
            out_dir=Path(args.out_dir) if args.out_dir else None,
            attr_name=args.attr,
            reset_target_tok_attr=args.reset,
        )
        print(f"apply-tok-refs: id2_slots={slots} target_writes={writes}")
        return 0
    if args.task == "aer":
        print(f"{compute_aer_from_files(args.gold, args.auto):.6f}")
        return 0
    if args.task == "segment-from-pivot":
        segment_from_pivot(args.level, args.pivot, args.target, args.output)
        return 0
    if args.task == "pushdown":
        stats = pushdown_file(
            input_path=Path(args.input),
            output_path=Path(args.output),
            from_level=args.from_level,
            to_level=args.to_level,
            template=args.template,
            overwrite=args.overwrite,
            index_source=args.index_source,
        )
        print(
            f"pushdown: parents={stats.parents_seen} children={stats.children_seen} "
            f"written={stats.children_written} skipped_existing={stats.children_skipped_existing}"
        )
        return 0
    if args.task == "migrate-histalign":
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for path in args.inputs:
            migrate_histalign_file(Path(path), out_dir / f"{Path(path).stem}.pair.json")
        return 0
    if args.task == "set":
        from .io.alignment_sets import (
            _DOC_META_UNSET,
            add_alignment_set_member,
            create_alignment_set_manifest,
            remove_alignment_set_member,
            set_alignment_set_pivot,
            update_alignment_set_member,
        )

        action = args.set_action
        root = project_root
        if action == "create":
            set_uid = (getattr(args, "id", None) or "").strip()
            if not set_uid:
                raise ValueError("set create requires --id")
            path = create_alignment_set_manifest(root, set_uid, title=args.title or "")
            print(path)
            return 0
        sid = (getattr(args, "set_id", None) or "").strip()
        if not sid:
            raise ValueError(f"set {action} requires --set <alignmentsetuid>")
        doc_path = getattr(args, "path", None)
        if action in {"add-doc", "remove-doc", "set-pivot", "update-doc"}:
            if not doc_path:
                raise ValueError(f"set {action} requires --path")
        if action == "add-doc":
            path = add_alignment_set_member(
                sid,
                doc_path,
                project_root=root,
                member_id=args.member_id,
                title=(args.title or "").strip() or None,
                witness=(args.witness or "").strip() or None,
                pivot=True if args.pivot else None,
            )
            print(path)
            return 0
        if action == "remove-doc":
            path = remove_alignment_set_member(sid, doc_path, project_root=root)
            print(path)
            return 0
        if action == "set-pivot":
            path = set_alignment_set_pivot(
                sid,
                doc_path,
                project_root=root,
                clear_others=not getattr(args, "keep_others", False),
            )
            print(path)
            return 0
        if action == "update-doc":
            vd = vars(args)
            witness_kw = vd["member_witness_update"] if "member_witness_update" in vd else _DOC_META_UNSET
            title_kw = vd["member_title_update"] if "member_title_update" in vd else _DOC_META_UNSET
            if witness_kw is _DOC_META_UNSET and title_kw is _DOC_META_UNSET:
                raise ValueError("set update-doc requires --member-witness and/or --member-title")
            path = update_alignment_set_member(
                sid,
                doc_path,
                project_root=root,
                witness=witness_kw,
                title=title_kw,
            )
            print(path)
            return 0
        raise ValueError(f"Unknown set action: {action}")
    if args.task == "info":
        from ._cli_info import main as info_main

        info_args = ["info", args.info_action, "--output-format", args.output_format]
        if getattr(args, "set_id", None):
            info_args.extend(["--set", args.set_id])
        if getattr(args, "project_root", None):
            info_args.extend(["--project-root", args.project_root])
        if getattr(args, "refresh_cache", False):
            info_args.append("--refresh-cache")
        return info_main(info_args)
    parser.print_help()
    return 0

