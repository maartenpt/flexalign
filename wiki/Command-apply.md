# Command: `apply`

Write **TUIDs** from pair or reconcile JSON onto **target TEI/XML** (writeback), using pivot alignment and optional invalidation flags.

```bash
flexalign apply alignments/pair.json --pivot witnessA.xml --project-root . --out-dir out/
```

## Arguments

- **`path`** — Pair JSON **or** reconcile JSON (`tuids` key selects reconcile mode).

## Flags

| Flag | Meaning |
| --- | --- |
| `--pivot` | **Required** for pair JSON: pivot TEI path (used to resolve pivot tuids / minting). |
| `--project-root` | Resolve relative `version1` / `version2` in JSON. |
| `--out-dir` | Write modified target XML here (else overwrite paths in JSON). |
| `--ignore-tuid-drift` | Do not abort when stored tuids differ from XML. |
| `--invalidate-below` | Strip `tuid` on elements not in the allowed set. |
| `--mark-needs-review` | Set `tuid-needs-review` when unexpected. |

## See also

- [Concepts](Concepts.md)
- [convert](Command-convert.md) — `to tei-writeback` uses the same apply logic.
