"""Shared CLI constants."""

from __future__ import annotations

import argparse

TASK_CHOICES = (
    "align",
    "cascade",
    "convert",
    "plain",
    "reconcile",
    "apply",
    "apply-tok-refs",
    "info",
    "install",
    "aer",
    "segment-from-pivot",
    "pushdown",
    "job",
    "migrate-histalign",
    "set",
)


def get_parent_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--verbose", action="store_true", help="Print progress messages")
    parser.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    return parser

