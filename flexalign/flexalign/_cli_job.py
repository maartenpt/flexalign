"""Simple job command shim."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flexalign job", allow_abbrev=False)
    parser.add_argument("action", choices=["status", "list", "kill"])
    parser.add_argument("--id", dest="job_id")
    args = parser.parse_args(argv[1:] if argv and argv[0] == "job" else argv)
    print({"action": args.action, "id": args.job_id})
    return 0

