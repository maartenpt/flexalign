# Command: `job`

Lightweight **placeholder** for future job control. Currently prints a small JSON-ish line to stdout.

```bash
flexalign job status --id 123
flexalign job list
flexalign job kill --id 123
```

## Arguments

- **`action`**: `status` | `list` | `kill`
- **`--id`** — Optional job id for `status` / `kill`.

## See also

- Not yet wired to a real job queue; safe to ignore unless you extend it.
