# flexalign

**flexalign** is a **command-line toolkit for parallel text alignment** over **TEI P5 / TEITOK-style XML**. It is aimed at corpus and edition workflows where you need stable links between two (or more) witnesses—at **text, chapter, paragraph, sentence, or token** granularity—without treating file order or line numbers as the source of truth.

In practice, flexalign helps you:

1. **Run alignments** between a *pivot* witness and a *target* witness using pluggable **backends** (from trivial identity matching to heavier neural or statistical options, depending on optional extras you install).
2. **Store results** in a small set of **JSON-first** formats (**pair JSON** for one pivot/target step, **reconcile JSON** when many pair files should agree on a single **translation-unit id**).
3. **Round-trip with XML**: read structure and optional **`@tuid`** (translation unit id) from TEI, align, then **apply** or **merge** tuids back onto the live files, or **convert** to interchange formats such as **TMX**, **Moses-style parallel text**, or a **fresh parallel TEI** export.

The design mirrors the idea behind tools like **flexipipe**: a **modular CLI** with a clear separation between **loading/normalization**, **alignment algorithms**, and **writers**—so you can script pipelines, keep human-readable manifests, and avoid locking alignment state inside a single GUI or proprietary format.

---

## What problems it is meant to solve

- **Parallel corpora and editions** where units must stay identifiable across versions, translators, or OCR passes.
- **TEITOK-oriented projects** that already use **`@tuid`** as the spine for “the same translation unit in another language or witness”; flexalign treats that spine as first-class while still using **`@xml:id`** (and related anchors) for precise element references in JSON and for writeback.
- **Interchange and tooling**: export to **TMX** or Moses lines for MT/tooling, or import from them, using an internal **alignment document (IR)** so conversions stay consistent.

It is *not* a general-purpose XML diff tool or a full TEI publisher; it focuses on **alignment rows**, **tuids**, and **witness paths** as the contract between steps.

---

## Core ideas (short)

| Idea | Role |
| --- | --- |
| **`@tuid`** | Canonical **translation-unit** identity across witnesses when present or after apply. |
| **`@xml:id` / anchors** | **Structural** hooks for each aligned row in pair JSON (`id1` / `id2`). |
| **Pair JSON** | One alignment artifact: pivot + target paths, `level`, `alignments[]` with `pairs[]` (text, scores, `tuid_at_write_*`, …). |
| **Reconcile JSON** | Many witnesses projected onto a shared **`tuids[]`** list with `members{ path → ids }`. |
| **Backends** | Produce pair rows; **apply** / **convert** consume them and update or emit files. |

For diagrams, defaults, and edge cases, see the wiki.

---

## Documentation

Detailed guides, installation, concepts, backends, and **one page per command** live in the Markdown wiki:

**[`wiki/`](wiki/README.md)** — start with [`wiki/Home.md`](wiki/Home.md) and [`wiki/Quick-Start.md`](wiki/Quick-Start.md).

At the shell, **`flexalign --help`** and **`flexalign <command> --help`** mirror the CLI.

---

## Install (minimal)

Requires **Python ≥ 3.9**. From a checkout or sdist:

```bash
pip install .
# optional backends / ML stacks: see wiki/Installation.md or: flexalign install
```

---

## License

MIT — see [`pyproject.toml`](pyproject.toml).
