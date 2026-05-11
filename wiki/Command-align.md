# Command: `align`

Run **one** alignment for a pivot/target pair (or for each pair resolved from an alignment **set**), and write **pair JSON**.

## Typical usage

```bash
flexalign align --pivot path/to/pivot.xml path/to/target.xml --output out.json --level s --backend identity
```

Or use a project set:

```bash
flexalign align --set myAlignmentSetUid --project-root /path/to/teitok/project --output out.json --level tok --backend awesome
```

## Main flags

| Flag | Meaning |
| --- | --- |
| `--pivot` | Two paths: pivot XML, target XML. |
| `--set` | Alignment set id (manifest); pairs come from the set plan. |
| `--pivot-mode` | `first` (default) or `all` when multiple pivots exist. |
| `--project-root` | Resolve relative paths in manifests / outputs. |
| `--output` | Required pair JSON path (multiple pairs get suffixed stems). |
| `--level` | Alignment level (e.g. `s`, `tok`; see [Concepts](Concepts.md)). |
| `--backend` | Backend name (`identity`, `attribute`, `awesome`, …). |
| `--attr` | For **attribute** backend: XML attribute to match on (default `xml:id`). |
| `--project-from-level` | Before aligning, run [`segment-from-pivot`](Command-segment-from-pivot.md) for each level from this value through `--level` (only `s` → `tok` chain is wired in CLI). |

## See also

- [cascade](Command-cascade.md) — multi-level batch.
- [Backends](Backends.md)
- [apply](Command-apply.md) — consume the JSON.
