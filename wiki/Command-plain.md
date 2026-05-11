# Command: `plain`

Work with **plain text** witnesses: segment into **minimal TEI** (with stable `xml:id` like `s0`, `s0_w0`, …), optionally detect language, then align or export.

Two subcommands (required):

## `plain prepare`

Turn a directory of text files into TEI suitable for **`align`** / **`cascade`**.

```bash
flexalign plain prepare --input-dir ./txts --out-dir ./tei --level s --segmenter builtin --manifest witnesses.json
```

| Flag | Meaning |
| --- | --- |
| `--input-dir` / `--out-dir` | Required directories. |
| `--glob` | Pattern (default `*.txt`). |
| `--recursive` | Use `rglob`. |
| `--level` | `s` or `tok`. |
| `--segmenter` | `builtin` (light rules) or `flexipipe` (`Document.from_plain_text`; flexipipe must be installed). |
| `--lang` | Optional `xml:lang` on generated `<text>`. |
| `--lang-detect` | Use **langdetect** if `[plain]` extra installed. |
| `--manifest` | Optional JSON summary of generated files. |

## `plain align-pair`

Align **two** `.txt` or TEI paths in one go (wraps `.txt` to TEI under `--work-dir`), writes **pair JSON**, optionally **TMX** / **Moses**.

```bash
flexalign plain align-pair en.txt de.txt --output pair.json --backend identity --level s
```

| Flag | Meaning |
| --- | --- |
| `pivot` / `target` | Positional paths. |
| `--output` | Pair JSON path. |
| `--work-dir` | TEI scratch dir for `.txt` inputs (default `.flexalign_plain_work`). |
| `--backend` / `--level` / `--attr` | Same as **align**. |
| `--segmenter` / `--lang` / `--lang-detect` | Same as **prepare** when wrapping text. |
| `--export-tmx` / `--tmx-lang-src` / `--tmx-lang-tgt` | Optional TMX after alignment. |
| `--export-moses-src` / `--export-moses-tgt` / `--export-moses-ids` | Optional Moses export. |

## See also

- [align](Command-align.md)
- [convert](Command-convert.md)
- [Installation](Installation.md) (`[plain]`, flexipipe)
