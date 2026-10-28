"""`flexalign merge`: many bitexts → one tuid system with minimal id lists (align/tuid_merge.py)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from .align.tuid_merge import POLICIES, from_reconcile_payload, merge_bitexts, to_reconcile_payload
    from .io.xces import iter_xces

    parser = argparse.ArgumentParser(
        prog="flexalign merge", allow_abbrev=False,
        description="Merge bitexts into one tuid system: units sharing an id are aligned; id lists are kept "
                    "as short as the alignments allow (one id per unit wherever possible).")
    parser.add_argument("--xces", nargs="+", default=[], metavar="FILE",
                        help="XCES alignment files (OPUS cesAlign, gzipped or not); each linkGrp is a bitext")
    parser.add_argument("--level", default="s", help="the level the ids are for (default: s)")
    parser.add_argument("--policy", choices=POLICIES, default="pivot",
                        help="pivot: documents without a bitext between them may be aligned through others "
                             "(default); exact: only what a bitext states")
    parser.add_argument("--prefix", default="t", help="id prefix (default: t → t1, t2, …)")
    parser.add_argument("--previous", type=Path, metavar="TUIDS_JSON",
                        help="an earlier merge result: ids keep their names where their members survive")
    parser.add_argument("--unify", type=Path, metavar="GROUPS_JSON",
                        help="copies of one document to unify first: {canonical name: [copy, …]}, names as the "
                             "bitexts use them (OPUS: the pivot document's copy per language pair)")
    parser.add_argument("--doc-root", type=Path, default=Path("."),
                        help="where the documents named in the bitexts are (for --unify; default: .)")
    parser.add_argument("--text-fallback", action="store_true",
                        help="--unify: match units by identical text in document order where the ids do not "
                             "(renumbered copies)")
    parser.add_argument("--min-overlap", type=float, default=0.5, metavar="SHARE",
                        help="--unify: a copy matching less than this share of its units is another version and "
                             "stays a document of its own (default: 0.5)")
    parser.add_argument("--output", type=Path, required=True, metavar="TUIDS_JSON",
                        help="the result in the reconcile format (tuids_<level>.json), with a report")
    args = parser.parse_args(argv[1:] if argv and argv[0] == "merge" else argv)

    bitexts = [bt for path in args.xces for bt in iter_xces(path)]
    if not bitexts:
        parser.error("no bitexts: give --xces FILE …")
    unification = None
    if args.unify:
        from .align.unify import rewrite_bitexts, unify_copies
        from .io.unit_texts import read_unit_texts

        groups = json.loads(args.unify.read_text(encoding="utf-8"))
        texts = {}
        for copies in groups.values():
            for doc in copies:
                path = args.doc_root / doc
                if not path.exists() and (args.doc_root / (doc + ".gz")).exists():
                    path = args.doc_root / (doc + ".gz")
                texts[doc] = read_unit_texts(path, level=args.level)
        unification = unify_copies(groups, texts, text_fallback=args.text_fallback, min_overlap=args.min_overlap)
        bitexts = rewrite_bitexts(bitexts, unification)
    previous = None
    if args.previous:
        previous = from_reconcile_payload(json.loads(args.previous.read_text(encoding="utf-8")))
    result = merge_bitexts(bitexts, policy=args.policy, prefix=args.prefix, previous=previous)
    payload = to_reconcile_payload(result, level=args.level)
    if unification is not None:
        payload["unify"] = {
            "documents": unification.report,
            "extras": {doc: [{"unit": e.unit[1], "from": list(e.source), "after": e.after} for e in extras]
                       for doc, extras in unification.extras.items()},
        }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    r = result.report
    print(f"{r['bitexts']} bitexts over {r['documents']} documents: {r['aligned_units']} aligned units, "
          f"{r['ids']} ids; {r['conflicting_components']} of {r['components']} components needed several ids, "
          f"{r['units_with_several_ids']} units have several (longest list {r['longest_list']})", file=sys.stderr)
    if result.multivalue:
        print("the ids are multivalue: declare the attribute so (TEITOK settings multivalue=\"1\" multisep=\"|\")",
              file=sys.stderr)
    if r["contradictions"]:
        print(f"{len(r['contradictions'])} pairs aligned by one bitext and kept apart by another: left unaligned",
              file=sys.stderr)
    if not r["ok"]:
        print(f"error: the ids do not express the bitexts ({r['missing_pairs']} pairs missing, "
              f"{r['forbidden_pairs']} wrongly aligned)", file=sys.stderr)
        return 1
    return 0
