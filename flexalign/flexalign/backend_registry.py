"""Backend registry and discovery."""

from __future__ import annotations

import importlib
import pkgutil
from importlib import metadata
from typing import Dict

from .backend_spec import BackendSpec

_REGISTRY: Dict[str, BackendSpec] = {}


def register_backend_spec(spec: BackendSpec) -> None:
    _REGISTRY[spec.name.lower()] = spec


def list_backends() -> Dict[str, BackendSpec]:
    return dict(_REGISTRY)


def get_backend(name: str) -> BackendSpec | None:
    return _REGISTRY.get(name.lower())


def _load_spec_from_module(module_name: str) -> BackendSpec | None:
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    spec = getattr(module, "BACKEND_SPEC", None)
    if isinstance(spec, BackendSpec):
        return spec
    return None


def _iter_builtin_specs():
    from . import backends as package

    prefix = package.__name__ + "."
    for module_info in pkgutil.iter_modules(package.__path__, prefix):
        spec = _load_spec_from_module(module_info.name)
        if spec:
            yield spec


def _iter_entrypoint_specs():
    try:
        entry_points = metadata.entry_points().select(group="flexalign.backends")
    except Exception:
        return
    for ep in entry_points:
        try:
            spec = ep.load()
        except Exception:
            continue
        if isinstance(spec, BackendSpec):
            yield spec


def discover_backends() -> None:
    for spec in _iter_builtin_specs():
        register_backend_spec(spec)
    for spec in _iter_entrypoint_specs() or ():
        register_backend_spec(spec)


discover_backends()

