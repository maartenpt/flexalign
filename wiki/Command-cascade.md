# Command: `cascade`

Run a **sequence of alignment levels** (steps) for one pivot/target pair, writing **one pair JSON file per step** into `--out-dir`.

## Typical usage

```bash
flexalign cascade --pivot pivot.xml target.xml --steps text,chapter,p,s --out-dir Alignments/Pairs
```

## Main flags

| Flag | Meaning |
| --- | --- |
| `--pivot` / `--set` / `--pivot-mode` / `--project-root` | Same resolution idea as [`align`](Command-align.md). |
| `--steps` | Comma-separated level names (default `text,chapter,p,s`). |
| `--backends` | Optional per-level overrides, e.g. `s:awesome,tok:attribute/tok`. |
| `--out-dir` | Directory for `pair_<pivot>_<target>_<level>.json`. |
| `--segment-from-pivot` | If set to a step name, run segmentation projection when that level is reached. |

## Behaviour notes

- For `s` / `tok`, cascade may call **segment_from_pivot** if units are missing (see `align/cascade.py`).
- Default backend per step is **identity** for coarse levels and **attribute** for finer ones unless overridden.

## See also

- [align](Command-align.md)
- [segment-from-pivot](Command-segment-from-pivot.md)
