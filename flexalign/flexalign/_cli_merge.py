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
    parser.add_argument("--output", type=Path, required=True, metavar="TUIDS_JSON",
                        help="the result in the reconcile format (tuids_<level>.json), with a report")
    args = parser.parse_args(argv[1:] if argv and argv[0] == "merge" else argv)

    bitexts = [bt for path in args.xces for bt in iter_xces(path)]
    if not bitexts:
        parser.error("no bitexts: give --xces FILE …")
    previous = None
    if args.previous:
        previous = from_reconcile_payload(json.loads(args.previous.read_text(encoding="utf-8")))
    result = merge_bitexts(bitexts, policy=args.policy, prefix=args.prefix, previous=previous)
    payload = to_reconcile_payload(result, level=args.level)
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
