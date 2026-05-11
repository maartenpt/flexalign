# Command: `apply-tok-refs`

From **pair JSON** only: copy pivot **`id1`** token ids onto the target’s **`@tok`** attribute (or `--attr` name) for each `id2` match. Does **not** modify `@tuid`.

```bash
flexalign apply-tok-refs alignments/pair.json --project-root . --out-dir out/
```

## Flags

| Flag | Meaning |
| --- | --- |
| `--project-root` | Resolve `version2` path. |
| `--out-dir` | Output directory for modified target. |
| `--attr` | Target attribute (default `tok`). |
| `--reset` | Clear existing `@tok` on all `<tok>` before applying. |

## See also

- [apply](Command-apply.md) — TUID writeback.
