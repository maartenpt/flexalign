# Contributing

## Layout

- **`flexalign/flexalign/`** — Python package (`align/`, `io/`, `backends/`, CLI modules).
- **`flexalign/tests/`** — pytest.
- **`wiki/`** — this documentation (Markdown).

## Tests

```bash
pip install -e ".[dev]"
PYTHONPATH=flexalign/flexalign python -m pytest flexalign/tests -q
```

## Backends

Add a module under `backends/` exporting **`BACKEND_SPEC`** (`BackendSpec`), or register an entry point in group **`flexalign.backends`**.

## Docs

When you add or rename CLI commands, update the matching **`wiki/Command-*.md`** and the tables in [README](README.md) / [Home](Home.md).
