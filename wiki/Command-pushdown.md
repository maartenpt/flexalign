# Command: `pushdown`

Generate **child-level** `@tuid` values from **parent-level** elements that already carry tuids (e.g. sentence → token), using a configurable template.

```bash
flexalign pushdown --input in.xml --output out.xml --from-level s --to-level tok --template "{parent}:w{index}"
```

## Flags

| Flag | Meaning |
| --- | --- |
| `--input` / `--output` | Required TEI paths. |
| `--from-level` | Parent level (e.g. `s`). |
| `--to-level` | Child level (e.g. `tok`). |
| `--template` | Format for new child tuids (`{parent}`, `{index}`, `{ord}`). |
| `--index-source` | `ord` (default) or `index`. |
| `--overwrite` | Replace existing child tuids where applicable. |

## See also

- [Concepts](Concepts.md) — TUID hierarchy.
