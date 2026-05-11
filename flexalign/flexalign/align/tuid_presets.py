"""Built-in tuid presets."""

from __future__ import annotations

HIERARCHICAL_PRESET = {
    "separator": ":",
    "segments": {
        "chapter": {"attribute": "n", "prefix": "ch", "counter": "parent", "separator": ":"},
        "p": {"attribute": "n", "prefix": "p", "counter": "parent", "separator": ":"},
        "s": {"attribute": "n", "prefix": "s", "counter": "parent", "separator": ":"},
        "tok": {"attribute": "n", "prefix": "w", "counter": "parent", "separator": ":"},
    },
}

FLAT_GLOBAL_PRESET = {
    "separator": "-",
    "segments": {
        "s": {"attribute": "", "prefix": "", "counter": "global", "separator": "-"},
        "tok": {"attribute": "", "prefix": "w", "counter": "parent", "separator": "."},
    },
}

