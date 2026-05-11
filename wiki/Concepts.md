# Concepts

## TUID (`@tuid`)

In TEITOK-oriented workflows, **`tuid`** identifies a **translation unit** across witnesses. flexalign can **read** existing `@tuid`, carry it in pair/reconcile JSON as `tuid_at_write_1` / `tuid_at_write_2`, and **write** or **merge** tuids onto target XML via [`apply`](Command-apply.md).

Multiple logical ids can be joined with **`|`** in one attribute; helpers in `align.tuid` parse and join without duplicating segments.

Long strings from external tools (e.g. TMX) can be **shortened** on export; see [Convert and formats](Convert-and-formats.md).

## TEI levels

Alignment operates on units discovered by **local tag name** in TEI/XML (see `AlignDoc.iter_units`):

| Level key | Typical element |
| --- | --- |
| `text` | `text` |
| `chapter` | `div` |
| `p` | `p` |
| `s` | `s` |
| `tok` | `tok` |

Unit identity for backends usually comes from **`@xml:id`** (or `@id`), with optional `@tuid` for pivot-derived identity.

## Pair JSON

The main interchange for one **pivot** / **target** pair:

- **`version1`**, **`version2`**: paths (often project-relative).
- **`level`**: alignment granularity (`s`, `tok`, …).
- **`alignments`**: list of groups; each has **`parent`** (optional hierarchy) and **`pairs`**.
- Each **pair row**: **`id1`** / **`id2`** (lists of anchors), **`text1`** / **`text2`**, **`score`**, **`tuid_at_write_*`**, optional **`alignment_basis`**, etc.

Produced by [`align`](Command-align.md), [`cascade`](Command-cascade.md), [`plain align-pair`](Command-plain.md), and consumed by [`apply`](Command-apply.md), [`reconcile`](Command-reconcile.md), [`convert`](Command-convert.md).

## Reconcile JSON

Merges several pair files into a single structure:

- **`documents`**: sorted list of witness paths.
- **`level`**: metadata.
- **`tuids`**: each item has **`tuid`**, optional **`parent_tuid`**, **`members`** map from document path → list of unit ids, **`confidence`**, **`needs_review`**.

## Alignment IR (internal)

Python dataclasses in `align.ir` (`AlignmentDocument`, `PairRow`, …) mirror pair/reconcile shapes for **convert** and tests. You do not need to use them from the CLI; they document the logical model behind **convert**.

## Alignment sets

TEITOK projects can define **sets** of documents (manifest on disk). The CLI [`set`](Command-set.md) and [`align --set`](Command-align.md) resolve **pivot/target pairs** from a set id. See [`info set-members`](Command-info.md).
