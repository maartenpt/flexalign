"""Dedicated info CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .backend_registry import list_backends
from .io.alignment_sets import (
    list_alignment_sets,
    list_pair_json_candidates_for_set,
    resolve_alignment_set_documents,
    resolve_alignment_set_members_detailed,
    resolve_alignment_set_plan,
)
from .io.view_fragments import (
    build_doc_tuid_levels_payload,
    build_fragment_payload,
    build_set_members_tuid_scan_payload,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flexalign info", allow_abbrev=False)
    parser.add_argument(
        "info_action",
        nargs="?",
        default="backends",
        choices=[
            "backends",
            "cascade-plan",
            "segmentation-projection",
            "tuid-scheme",
            "sets",
            "set-members",
            "fragment",
            "doc-tuid-levels",
            "set-tuid-levels",
        ],
    )
    parser.add_argument("--output-format", choices=["table", "json"], default="table")
    parser.add_argument("--set", dest="set_id")
    parser.add_argument("--project-root")
    parser.add_argument("--doc", dest="fragment_doc", help="Manifest doc path (set-members path) for fragment extraction.")
    parser.add_argument("--level", default="s")
    parser.add_argument("--anchor", default="")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--context", type=int, default=3)
    parser.add_argument("--include-front", action="store_true")
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force refresh of cached virtual set expansion.",
    )
    parser.add_argument(
        "--paths",
        default="",
        help="Comma-separated project-relative TEI paths (exactly two) for doc-tuid-levels.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:] if argv and argv[0] == "info" else argv)
    project_root = Path(args.project_root).resolve() if args.project_root else Path.cwd()
    if args.info_action == "backends":
        payload = {"backends": sorted(list_backends().keys())}
    elif args.info_action == "cascade-plan":
        payload = {"steps": []}
    elif args.info_action == "segmentation-projection":
        payload = {"implemented_levels": ["s"], "scaffolded_levels": ["p", "div", "text"]}
    elif args.info_action == "sets":
        payload = {"sets": list_alignment_sets(project_root=project_root, force_refresh=bool(args.refresh_cache))}
    elif args.info_action == "set-members":
        if not args.set_id:
            raise SystemExit("--set is required for `info set-members`")
        plan = resolve_alignment_set_plan(
            args.set_id, project_root=project_root, force_refresh=bool(args.refresh_cache)
        )
        payload = {
            "set": args.set_id,
            "pivot": plan["pivot"],
            "pivots": plan.get("pivots", []),
            "pairs": plan.get("pairs", []),
            "documents": resolve_alignment_set_documents(
                args.set_id, project_root=project_root, force_refresh=bool(args.refresh_cache)
            ),
            "members": resolve_alignment_set_members_detailed(
                args.set_id, project_root=project_root, force_refresh=bool(args.refresh_cache)
            ),
            "pair_json_candidates": list_pair_json_candidates_for_set(
                args.set_id, project_root=project_root, max_files=200
            ),
        }
    elif args.info_action == "fragment":
        lo = max(1, min(200, args.limit))
        off = max(0, args.offset)
        ctx = max(0, min(200, args.context))
        if not args.set_id or not args.fragment_doc:
            msg = "--set and --doc are required for `info fragment`"
            if args.output_format == "json":
                payload = {
                    "set": args.set_id or "",
                    "doc": args.fragment_doc or "",
                    "level": args.level,
                    "anchor": args.anchor,
                    "offset": off,
                    "limit": lo,
                    "context": ctx,
                    "items": [],
                    "has_more": False,
                    "next_offset": 0,
                    "placeholder": False,
                    "message": msg,
                }
            else:
                raise SystemExit(msg)
        else:
            try:
                payload = build_fragment_payload(
                    set_id=args.set_id,
                    doc_key=args.fragment_doc,
                    project_root=project_root,
                    level=args.level,
                    anchor=args.anchor,
                    offset=off,
                    limit=lo,
                    context=ctx,
                    include_front=bool(args.include_front),
                )
            except Exception as exc:
                # Must print JSON to stdout for TEITOK/tuview; uncaught errors only reach stderr via __main__.
                err = f"{type(exc).__name__}: {exc}"
                if args.output_format != "json":
                    raise SystemExit(err) from exc
                payload = {
                    "set": args.set_id,
                    "doc": args.fragment_doc,
                    "level": args.level,
                    "anchor": args.anchor,
                    "offset": off,
                    "limit": lo,
                    "context": ctx,
                    "items": [],
                    "has_more": False,
                    "next_offset": 0,
                    "placeholder": False,
                    "message": err,
                }
    elif args.info_action == "doc-tuid-levels":
        raw = (args.paths or "").strip()
        if not raw:
            msg = "--paths is required for `info doc-tuid-levels` (two comma-separated TEI paths)"
            if args.output_format == "json":
                payload = {
                    "paths": [],
                    "error": msg,
                    "per_file": {},
                    "intersection_levels": [],
                    "align_level": None,
                    "project_from_level": None,
                    "reason": "",
                }
            else:
                raise SystemExit(msg)
        else:
            parts = [p.strip().replace("\\", "/") for p in raw.split(",") if p.strip()]
            payload = build_doc_tuid_levels_payload(project_root, parts[:2])
    elif args.info_action == "set-tuid-levels":
        if not args.set_id:
            msg = "--set is required for `info set-tuid-levels`"
            if args.output_format == "json":
                payload = {"set": "", "members": [], "error": msg}
            else:
                raise SystemExit(msg)
        else:
            payload = build_set_members_tuid_scan_payload(
                args.set_id,
                project_root=project_root,
                force_refresh=bool(args.refresh_cache),
            )
    else:
        payload = {"scheme": "resolved at runtime"}
    if args.output_format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload)
    return 0

