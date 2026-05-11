"""Lazy subcommand router."""

from __future__ import annotations

import sys

from ._cli_shared import TASK_CHOICES


def _subcommand_from_argv(argv: list[str]) -> str | None:
    for arg in argv:
        if not arg.startswith("-") and arg in TASK_CHOICES:
            return arg
    return None


def run(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    subcommand = _subcommand_from_argv(args)
    if subcommand == "info":
        from ._cli_info import main

        return main(args)
    if subcommand == "install":
        from ._cli_install import main

        return main(args)
    if subcommand == "job":
        from ._cli_job import main

        return main(args)
    from ._cli import main

    return main(args)

