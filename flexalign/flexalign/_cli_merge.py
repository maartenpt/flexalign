"""`flexalign merge`: many bitexts → one tuid system with minimal id lists (align/tuid_merge.py)."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from .align.tuid_merge import POLICIES, from_reconcile_payload, merge_bitexts, write_reconcile_payload
    from .io.pair_json import read_pair_bitext
    from .io.xces import iter_xces
    from . import progress
    from .progress import Progress, duration, track

    parser = argparse.ArgumentParser(
        prog="flexalign merge", allow_abbrev=False,
        description="Merge bitexts into one tuid system: units sharing an id are aligned; id lists are kept "
                    "as short as the alignments allow (one id per unit wherever possible).")
    parser.add_argument("--xces", nargs="+", default=[], metavar="FILE",
                        help="XCES alignment files (OPUS cesAlign, gzipped or not); each linkGrp is a bitext")
    parser.add_argument("--pairs", nargs="+", default=[], metavar="FILE",
                        help="flexalign pair JSON files (`flexalign align` output, e.g. token pairs); documents "
                             "named relative to --doc-root")
    parser.add_argument("--level", default="s", help="the level the ids are for (default: s)")
    parser.add_argument("--policy", choices=POLICIES, default="pivot",
                        help="pivot: documents without a bitext between them may be aligned through others "
                             "(default); exact: only what a bitext states")
    parser.add_argument("--prefix", default="t", help="id prefix (default: t → t1, t2, …)")
    parser.add_argument("--previous", type=Path, metavar="TUIDS_JSON",
                        help="an earlier merge result: ids keep their names where their members survive")
    parser.add_argument("--unify", type=Path, metavar="GROUPS_JSON",
                        help="copies of one document to unify first: {canonical name: [copy, …]}, names as the "
                             "bitexts use them (OPUS: the pivot document's copy per language pair); a document listed as its "
                             "own only copy is left as it is")
    parser.add_argument("--doc-root", type=Path, default=Path("."),
                        help="where the documents named in the bitexts are (for --unify and --pairs; default: .)")
    parser.add_argument("--text-fallback", action="store_true",
                        help="--unify: match units by identical text in document order where the ids do not "
                             "(renumbered copies)")
    parser.add_argument("--min-overlap", type=float, default=0.5, metavar="SHARE",
                        help="--unify: a copy matching less than this share of its units is another version and "
                             "stays a document of its own (default: 0.5)")
    parser.add_argument("--output", type=Path, required=True, metavar="TUIDS_JSON",
                        help="the result in the reconcile format (tuids_<level>.json), with a report")
    args = parser.parse_args(argv[1:] if argv and argv[0] == "merge" else argv)

    started = time.time()
    bitexts = [bt for path in track(args.xces, "read alignments", name=lambda p: Path(p).name)
               for bt in iter_xces(path)]
    if args.pairs:
        bitexts += [read_pair_bitext(path, doc_root=args.doc_root)
                    for path in track(args.pairs, "read pairs", name=lambda p: Path(p).name)]
    if not bitexts:
        parser.error("no bitexts: give --xces FILE … or --pairs FILE …")
    unification = None
    if args.unify:
        from .align.unify import rewrite_bitexts, unify_copies
        from .io.unit_texts import read_unit_texts

        groups = json.loads(args.unify.read_text(encoding="utf-8"))
        # a document that is its own only copy has nothing to unify: not read (Europarl: all of them)
        groups = {c: copies for c, copies in groups.items() if list(copies) != [c]}
        texts = {}
        for doc in track([d for copies in groups.values() for d in copies], "read documents", name=str):
            path = args.doc_root / doc
            if not path.exists() and (args.doc_root / (doc + ".gz")).exists():
                path = args.doc_root / (doc + ".gz")
            texts[doc] = read_unit_texts(path, level=args.level)
        with Progress("unify copies", len(groups)) as p:
            unification = unify_copies(groups, texts, text_fallback=args.text_fallback,
                                       min_overlap=args.min_overlap, on_group=p.step)
        bitexts = rewrite_bitexts(bitexts, unification)
    # what was read lives to the end: kept out of the garbage collector's passes, which on millions of objects
    # cost minutes (more when memory is short); the merge itself makes no reference cycles
    gc.freeze()
    gc.disable()
    previous = None
    if args.previous:
        previous = from_reconcile_payload(json.loads(args.previous.read_text(encoding="utf-8")))
    result = merge_bitexts(bitexts, policy=args.policy, prefix=args.prefix, previous=previous, progress=Progress)
    with Progress("free the alignments read"):   # no longer needed: freed before the result is written
        del bitexts
    extra = {}
    if unification is not None:
        extra["unify"] = {
            "documents": unification.report,
            "extras": {doc: [{"unit": e.unit[1], "from": list(e.source), "after": e.after} for e in extras]
                       for doc, extras in unification.extras.items()},
        }
    with Progress(f"write {args.output.name}", len(result.groups)) as p:
        write_reconcile_payload(args.output, result, level=args.level, extra=extra, on_id=p.step)
    if progress.enabled:
        print(f"  merge done in {duration(time.time() - started)}", file=sys.stderr)

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
