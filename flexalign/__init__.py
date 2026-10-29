"""Top-level package wrapper for nested source layout.

Exposes `flexalign.align`, `flexalign.backends`, `flexalign.io` and `flexalign.progress`
as aliases to the implementation package at `flexalign.flexalign.*`.
"""

from __future__ import annotations

import sys

from .flexalign import __version__, align, backends, io, progress

# Re-export common modules at the public package path.
sys.modules[__name__ + ".align"] = align
sys.modules[__name__ + ".backends"] = backends
sys.modules[__name__ + ".io"] = io
sys.modules[__name__ + ".progress"] = progress

