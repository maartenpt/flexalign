# Command: `convert`

Transform alignment data **from** one serialized format **to** another, using the internal alignment IR.

```bash
flexalign convert --from tmx --to teitok --input corpus.tmx --output corpus.tei.xml --lang-src en --lang-tgt de
```

## Required

- `--from` — `pair` | `reconcile` | `tmx` | `moses`
- `--to` — `pair` | `reconcile` | `tmx` | `moses` | `teitok` | `tei-writeback`
- `--input` — primary file (pair JSON, reconcile JSON, TMX, or Moses **source** side).
- `--output` — primary output path (meaning depends on target format).

## Often needed

| Flag | When |
| --- | --- |
| `--moses-secondary` | **from** or **to** `moses`: path to the other language’s line file. |
| `--version1` / `--version2` | **from reconcile**: document keys inside `members`. |
| `--lang-src` / `--lang-tgt` | **tmx** / **teitok** `xml:lang` (optional; from TMX `srclang` / `tuv` when omitted). |
| `--pivot` / `--project-root` / `--out-dir` | **to tei-writeback**: existing TEI writeback (see [Convert and formats](Convert-and-formats.md)). |
| `--tuid-prefix` | **tmx** / **teitok**: emit `PREFIX-s1`, `PREFIX-s2`, … (or `-w1`, … at `--level tok`). |
| `--tuid-max-length` | **tmx** / **teitok** when no prefix: shorten long fragments to `t`+hex (default `0` = verbatim). |
| `--compact-tuids` | After load, rewrite **all** `tuid_at_write_*` (ordinal if `--tuid-prefix`, else hash per max length). |

## See also

- [Convert and formats](Convert-and-formats.md) — format details.
- [Concepts](Concepts.md)
