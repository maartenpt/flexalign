"""Install helper command."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flexalign install", allow_abbrev=False)
    parser.add_argument("backend", nargs="?", choices=["awesome", "hunalign", "labse"])
    args = parser.parse_args(argv[1:] if argv and argv[0] == "install" else argv)
    if not args.backend:
        parser.print_help()
        return 0
    print(f"Install backend extras with: pip install \"flexalign[{args.backend}]\"")
    return 0

