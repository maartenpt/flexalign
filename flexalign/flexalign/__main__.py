"""Entry point for python -m flexalign."""

from __future__ import annotations

import os
import sys

from . import __version__

if "--version" in sys.argv or "-V" in sys.argv:
    print(f"flexalign {__version__}")
    raise SystemExit(0)

from ._cli_router import run


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    debug_enabled = os.environ.get("FLEXALIGN_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
    try:
        return run(args)
    except KeyboardInterrupt:
        print("[flexalign] Interrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        if debug_enabled:
            raise
        print(f"[flexalign] Error: {exc}", file=sys.stderr)
        print("[flexalign] Set FLEXALIGN_DEBUG=1 to show traceback.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

