# Command: `reconcile`

Merge **multiple pair JSON files** into a single **reconcile JSON** keyed by TUID (`tuid_at_write_1` per row, or `auto:tuid` when missing).

```bash
flexalign reconcile --level s pair_a.json pair_b.json --output merged.json
```

## Flags

| Flag | Meaning |
| --- | --- |
| `--level` | Required metadata on output payload. |
| `pair_files` | One or more pair JSON paths (positional). |
| `--output` | Reconcile JSON path. |
| `--ignore-tuid-drift` | Skip XML drift checks when `version1`/`version2` paths exist and XML is readable. |

## Drift checks

When pair files reference TEI on disk, reconcile can verify that stored `tuid_at_write_*` still match live `@tuid` on elements (unless `--ignore-tuid-drift`).

## See also

- [Concepts](Concepts.md) — reconcile shape.
- [convert](Command-convert.md) — `from reconcile` / `to reconcile`.
