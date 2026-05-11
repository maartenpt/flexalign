# Command: `aer`

Compute **alignment error rate** (AER) between a gold and an automatic alignment file (implementation-specific file format expected by `align/aer.py`).

```bash
flexalign aer gold.json auto.json
```

## Arguments

- **`gold`** — reference alignment file path.
- **`auto`** — system alignment file path.

Output is a single numeric line (stdout).

## See also

- [align](Command-align.md) — produce automatic pair JSON.
