# Command: `set`

Manage **alignment set manifests** on disk (create set, add/remove documents, mark pivot, update metadata).

```bash
flexalign set create --id mySet --title "Parallel corpus" --project-root .
flexalign set add-doc --set mySet --path Texts/en.xml --witness en --pivot --project-root .
```

## Actions

| Action | Required flags |
| --- | --- |
| **create** | `--id` (set uid); optional `--title`. |
| **add-doc** | `--set`, `--path`; optional `--member-id`, `--title`, `--witness`, `--pivot`. |
| **remove-doc** | `--set`, `--path`. |
| **set-pivot** | `--set`, `--path`; optional `--keep-others`. |
| **update-doc** | `--set`, `--path`; at least one of `--member-witness` / `--member-title`. |

## Flags

| Flag | Meaning |
| --- | --- |
| `--project-root` | TEITOK project root. |

## See also

- [align](Command-align.md) — `--set` to align all pairs from a set.
- [info set-members](Command-info.md)
