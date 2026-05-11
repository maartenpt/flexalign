# Installation

## Requirements

- **Python** ≥ 3.9 (see project `pyproject.toml`).
- **lxml** is the main runtime dependency.

## Install

From the repository root (or a published package):

```bash
pip install -e .
```

Optional feature groups:

| Extra | Purpose |
| --- | --- |
| `flexalign[plain]` | `langdetect` for `flexalign plain prepare` / `align-pair` when using `--lang-detect`. |
| `flexalign[awesome]` | Transformers + Torch for the **awesome** backend. |
| `flexalign[labse]` | Sentence-transformers + PolyFuzz for the **labse** scaffold backend. |
| `flexalign[dev]` | pytest, pytest-cov. |

```bash
pip install -e ".[plain,dev]"
```

**flexipipe** (sibling project) is **not** a declared dependency. For `plain --segmenter flexipipe`, install flexipipe in the same environment (`pip install -e ../flexipipe` or similar).

## CLI entry point

After install:

```bash
flexalign --help
python -m flexalign --help
```

Use **`FLEXALIGN_DEBUG=1`** to print tracebacks on errors (see `flexalign.__main__`).
