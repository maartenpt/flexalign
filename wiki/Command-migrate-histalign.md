# Command: `migrate-histalign`

Convert **legacy histalign** JSON files into modern **pair JSON** shape (`io/jsonio.migrate_histalign_payload`).

```bash
flexalign migrate-histalign old1.json old2.json --out migrated/
```

## Arguments

- **`inputs`** — One or more histalign JSON paths.
- **`--out`** — Required output **directory**; each input becomes `stem.pair.json` there.

## See also

- [Concepts](Concepts.md) — pair JSON shape.
