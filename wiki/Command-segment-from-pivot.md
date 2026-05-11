# Command: `segment-from-pivot`

Project **segmentation** from a **pivot** TEI document onto a **target** TEI document for a given structural **level** (e.g. create missing `<s>` / `<tok>` structure on the target based on pivot).

```bash
flexalign segment-from-pivot --level s --pivot pivot.xml --target target.xml --output target-segmented.xml
```

## Flags

| Flag | Meaning |
| --- | --- |
| `--level` | Required (e.g. `s`, `tok`). |
| `--pivot` | Pivot TEI path. |
| `--target` | Target TEI path. |
| `--output` | Optional output path (behaviour defined in `align/projection.py`). |

Used internally from **`align --project-from-level`** and parts of **`cascade`**.

## See also

- [align](Command-align.md)
- [cascade](Command-cascade.md)
