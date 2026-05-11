"""Input/output registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional


@dataclass
class InputEntry:
    name: str
    aliases: tuple[str, ...]
    loader: Callable[..., object]


@dataclass
class OutputEntry:
    name: str
    aliases: tuple[str, ...]
    saver: Callable[..., None]


class IORegistry:
    def __init__(self) -> None:
        self._inputs: Dict[str, InputEntry] = {}
        self._outputs: Dict[str, OutputEntry] = {}

    def register_input(self, entry: InputEntry) -> None:
        self._inputs[entry.name.lower()] = entry
        for alias in entry.aliases:
            self._inputs[alias.lower()] = entry

    def register_output(self, entry: OutputEntry) -> None:
        self._outputs[entry.name.lower()] = entry
        for alias in entry.aliases:
            self._outputs[alias.lower()] = entry

    def get_input(self, name: str) -> Optional[InputEntry]:
        return self._inputs.get(name.lower())

    def get_output(self, name: str) -> Optional[OutputEntry]:
        return self._outputs.get(name.lower())


registry = IORegistry()

