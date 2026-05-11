"""Backend definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional, Protocol

BackendFactory = Callable[..., "AlignBackend"]


@dataclass(frozen=True)
class StepSpec:
    parent_level: str | None
    level: str
    mode: Literal["direct", "rollup"]
    via: str | None = None
    needs_pretokenized: bool = False


class AlignBackend(Protocol):
    name: str
    supported_steps: tuple[StepSpec, ...]

    def align(self, src: Any, tgt: Any, *, step: StepSpec, parent_pairs: list[dict], options: dict) -> dict:
        ...


@dataclass(frozen=True)
class BackendSpec:
    name: str
    description: str
    factory: BackendFactory
    supported_steps: tuple[StepSpec, ...] = field(default_factory=tuple)
    url: Optional[str] = None
    install_instructions: Optional[str] = None

