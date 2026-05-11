# flexalign

**flexalign** is a modular CLI for **parallel text alignment** over TEI/XML (including TEITOK-style markup). It treats **`@tuid`** (translation unit id) as the canonical spine for identity across witnesses, while still using **`@xml:id`** / structural attributes for anchoring rows in pair JSON and for writeback into XML.

Typical uses:

- Align two TEI witnesses at **text / chapter / paragraph / sentence / token** levels.
- **Reconcile** several pair JSON files into one TUID-keyed view.
- **Apply** alignments back onto XML (set or merge `@tuid` on the target).
- **Convert** between **pair JSON**, **reconcile JSON**, **TMX**, **Moses-style parallel text**, and **new TEI (teitok export)**.
- **Prepare** plain-text directories into minimal TEI, then align or export.

Run **`flexalign --help`** or **`flexalign <command> --help`** for the full argparse text.

---

## Commands

| Command | Purpose |
| --- | --- |
| [`align`](Command-align.md) | Run a single alignment step for one pivot/target pair (or set); write pair JSON. |
| [`cascade`](Command-cascade.md) | Run a **sequence** of levels with per-level backends; write multiple pair JSON files. |
| [`convert`](Command-convert.md) | Convert alignment between **pair**, **reconcile**, **TMX**, **Moses**, **teitok** (new TEI), **tei-writeback** (apply tuids). |
| [`plain`](Command-plain.md) | **prepare**: directory of `.txt` → minimal TEI; **align-pair**: two files → pair JSON (optional TMX/Moses export). |
| [`reconcile`](Command-reconcile.md) | Merge multiple pair JSON files into one reconcile JSON keyed by TUID. |
| [`apply`](Command-apply.md) | Apply pair or reconcile JSON to XML (propagate `@tuid` onto target). |
| [`apply-tok-refs`](Command-apply-tok-refs.md) | Write pivot token ids onto target **`@tok`** (or another attribute); does not change `@tuid`. |
| [`info`](Command-info.md) | Inspect backends, alignment sets, fragments, TUID coverage, doc levels, etc. |
| [`install`](Command-install.md) | Print pip extra hints for optional backends. |
| [`aer`](Command-aer.md) | Compute alignment error rate between two pair-style files. |
| [`segment-from-pivot`](Command-segment-from-pivot.md) | Project segmentation from pivot TEI onto target. |
| [`pushdown`](Command-pushdown.md) | Generate child-level **tuid** values from parent-level tuids. |
| [`job`](Command-job.md) | Placeholder job control (status/list/kill). |
| [`migrate-histalign`](Command-migrate-histalign.md) | Convert legacy histalign JSON to pair JSON shape. |
| [`set`](Command-set.md) | Create/update **alignment set** manifests (members, pivot). |

---

## Key ideas

- **Pair JSON**: pivot/target paths, `level`, `alignments[]` with `parent` + `pairs` (`id1`, `id2`, `tuid_at_write_*`, scores, …). See [Concepts](Concepts.md).
- **Reconcile JSON**: `tuids[]` with `members{ document_path: [xml:ids…] }` for many witnesses. See [Concepts](Concepts.md).
- **Backends** compute rows; **apply** mutates XML. See [Backends](Backends.md).
- **Convert** uses an internal **alignment document** (IR) for many formats; see [Convert and formats](Convert-and-formats.md).

---

## Wiki index

- [Installation](Installation.md)
- [Quick Start](Quick-Start.md)
- [Concepts](Concepts.md)
- [Backends](Backends.md)
- [Convert and formats](Convert-and-formats.md)
- [Contributing](Contributing.md)
- All command pages are listed in [README](README.md).
