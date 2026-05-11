# Convert and formats

The [`convert`](Command-convert.md) command loads an **alignment document** (IR) from one format and saves another.

## `--from` loaders

| Value | Input |
| --- | --- |
| **pair** (aliases: `pair-json`, `json`) | Pair JSON file. |
| **reconcile** | Reconcile JSON; requires **`--version1`** and **`--version2`** paths matching `members` keys. |
| **tmx** | TMX 1.4 file; optional **`--lang-src`** / **`--lang-tgt`** to pick ``tuv`` sides (relaxed BCP47). If omitted: uses **``<tu srclang>``** when present, else first/second ``tuv``; stores **`tmx_lang_src`** / **`tmx_lang_tgt`** on the document for **teitok**/**tmx** export when language flags are omitted. |
| **moses** | Parallel plain text; **`--input`** = source side, **`--moses-secondary`** = target side; optional **`--ids-path`**. |

## `--to` writers

| Value | Output |
| --- | --- |
| **pair** | Pair JSON. |
| **reconcile** | Reconcile JSON (single-pair projection). |
| **tmx** | TMX 1.4; uses `x-flexalign:id1` / `id2` props for round-trip anchors when present. |
| **moses** | Two line files; **`--output`** = source path, **`--moses-secondary`** = target path; optional **`--moses-ids-out`**. |
| **teitok** (aliases: **`tei`**, `tei-new`, `tei-parallel`) | **New** TEI P5 file: ``flexalign-import`` → two ``flexalign-witness`` columns (pivot then target) with full ``xml:lang`` on each column; all `<s>` / `<tok>` for that language in row order; ``@tuid`` links rows across columns; no repeated ``xml:lang`` on each unit; not writeback. |
| **tei-writeback** (alias: **`xml-writeback`**) | Apply tuids to **existing** XML via pivot + pair paths; requires **`--pivot`**, **`--project-root`**, etc. |

## TUIDs on TMX / teitok export

- **`--tuid-prefix`**: when set, each alignment row gets a readable **`PREFIX-s1`**, **`PREFIX-s2`**, … (or **`PREFIX-w1`**, … when **`--level tok`**). The prefix is sanitized for XML (use a corpus or set id you choose, e.g. `vec.common-voice-conv`). This overrides source tuids for **`tuid`** / **`@tuid`** on those exports.
- **`--tuid-max-length`** (default **0**): when **no** `--tuid-prefix`, fragments longer than *N* characters are shortened to **`t` + 20 hex** (blake2b). **`0`** keeps verbatim source tuids.
- **`--compact-tuids`**: after load, rewrite **all** `tuid_at_write_*` in the IR. With **`--tuid-prefix`**, uses the same ordinal scheme; otherwise uses **`--tuid-max-length`**, defaulting to **56** for hash compaction when max is **0** (so plain `--compact-tuids` still shortens long tuids for **pair** / **reconcile** export).

## See also

- [Command-convert](Command-convert.md) for the full flag list.
- [Concepts](Concepts.md) for pair vs reconcile shapes.
