# Alignment backends

Backends implement **one alignment step**: given two loaded TEI documents (`AlignDoc`), they return a list of **pair rows** (`id1`, `id2`, `text1`, `text2`, scores, `tuid_at_write_*`, …).

Discovery: built-in modules under `flexalign.backends` export **`BACKEND_SPEC`**; optional plugins can register via the **`flexalign.backends`** entry point group (see `backend_registry.py`).

## Built-in backends

| Name | Role |
| --- | --- |
| **identity** | Match units that share the same anchor id (`xml:id` / `id`); copy `@tuid` when present. |
| **attribute** | Match on a configurable XML attribute (`--attr`, default `n`), with optional verse-style normalization. |
| **hunalign** | Scaffold: currently delegates to **identity**. |
| **labse** | Scaffold: delegates to **identity**; optional extras documented under [`install`](Command-install.md). |
| **awesome** | Neural token alignment at **`tok`** (sentence-grouped); non-`tok` levels delegate to **identity**. Requires `[awesome]` extras. |

List names at runtime:

```bash
flexalign info backends
```

## Cascade backend map

[`cascade`](Command-cascade.md) accepts **`--backends`** as comma-separated **`level:backend`** or **`level:backend/mode`** overrides for specific steps.

## Further reading

- [`align`](Command-align.md) — `--backend`, `--attr`, `--level`.
- [`cascade`](Command-cascade.md) — multi-step runs.
