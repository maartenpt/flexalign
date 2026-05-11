# Command: `info`

Inspect project state, backends, and TEITOK-oriented payloads. Default action is **`backends`**.

```bash
flexalign info backends
flexalign info set-members --set mySet --project-root . --output-format json
```

## Actions

| Action | Purpose |
| --- | --- |
| **backends** | List registered alignment backend names. |
| **cascade-plan** | Placeholder payload (scaffold). |
| **segmentation-projection** | Which projection levels are implemented vs scaffolded. |
| **tuid-scheme** | Short scheme description payload. |
| **sets** | List alignment sets under `--project-root`. |
| **set-members** | Requires **`--set`**: pivot(s), pairs, documents, detailed members. |
| **fragment** | Requires **`--set`** and **`--doc`**: aligned fragments for UI (`build_fragment_payload`). |
| **doc-tuid-levels** | Requires **`--paths`**: two comma-separated TEI paths; suggests align / project-from levels from `@tuid` coverage. |
| **set-tuid-levels** | Requires **`--set`**: per-member `@tuid` counts by TEI level. |

## Common flags

| Flag | Meaning |
| --- | --- |
| `--output-format` | `table` (default) or `json`. |
| `--project-root` | Project root (default cwd). |
| `--set` | Alignment set id for set-scoped actions. |
| `--refresh-cache` | Force refresh of cached virtual set expansion. |
| **fragment** | `--doc`, `--level`, `--anchor`, `--offset`, `--limit`, `--context`, `--include-front`. |

## See also

- [set](Command-set.md)
- [Concepts](Concepts.md)
