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

