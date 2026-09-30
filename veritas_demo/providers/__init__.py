"""Provider discovery for upstream capability implementations.

A provider resolves one named upstream capability to an importable module.
Resolution order is explicit and reported, never silently guessed:

1. ``VERITAS_<NAME>_PATH`` environment variable (absolute path to a .py file
   or a directory to place on ``sys.path``)
2. an already-importable top-level module on ``sys.path``
3. the paths in the ``veritas.providers.json`` search list

When nothing resolves, the capability is reported as ``UNAVAILABLE``. Veritas
does not fall back to a built-in reimplementation.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ENV_PREFIX = "VERITAS_"

#: capability name -> (env var suffix, dotted module, required attributes)
REQUIREMENTS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "registry": ("REGISTRY_PATH", "state_registry", ("StateRegistry",)),
    "predicate_semantics": (
        "PREDICATE_SEMANTICS_PATH",
        "predicate_semantics",
        ("PREDICATES", "get", "self_check"),
    ),
    "writeback_validator": (
        "WRITEBACK_VALIDATOR_PATH",
        "writeback_validator",
        ("Edge", "validate", "self_check"),
    ),
    "outcome_taxonomy": (
        "OUTCOME_TAXONOMY_PATH",
        "outcome_taxonomy",
        ("ALL_CLASSES", "family", "summarise"),
    ),
    "capability_inventory": (
        "CAPABILITY_INVENTORY_PATH",
        "capability_inventory",
        ("query",),
    ),
}

_CONFIG_NAME = "veritas.providers.json"


@dataclass
class Resolution:
    """How (or whether) one upstream capability was resolved."""

    capability: str
    module_name: str
    source: str
    detail: str = ""
    module: Any = None
    missing_attributes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.module is not None and not self.missing_attributes

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "module": self.module_name,
            "source": self.source,
            "detail": self.detail,
            "resolved": self.ok,
            "missing_attributes": list(self.missing_attributes),
        }


@dataclass
class ProviderSet:
    """The resolved provider modules for one Veritas session."""

    resolutions: dict[str, Resolution] = field(default_factory=dict)

    def module(self, capability: str) -> Any:
        res = self.resolutions.get(capability)
        return res.module if res and res.ok else None

    def is_available(self, capability: str) -> bool:
        res = self.resolutions.get(capability)
        return bool(res and res.ok)

    def require(self, capability: str) -> Any:
        mod = self.module(capability)
        if mod is None:
            res = self.resolutions.get(capability)
            raise CapabilityUnavailable(capability, res.detail if res else "not resolved")
        return mod

    def as_dict(self) -> dict[str, Any]:
        return {name: res.as_dict() for name, res in sorted(self.resolutions.items())}


class CapabilityUnavailable(RuntimeError):
    """Raised when a required upstream capability could not be resolved."""

    def __init__(self, capability: str, detail: str = "") -> None:
        super().__init__(f"capability {capability!r} unavailable: {detail}")
        self.capability = capability
        self.detail = detail


def config_path() -> Path:
    """Location of the optional provider search-path configuration."""
    return Path(__file__).resolve().parent.parent / _CONFIG_NAME


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def _load_from_file(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_one(capability: str, cfg: dict[str, Any]) -> Resolution:
    env_suffix, module_name, required = REQUIREMENTS[capability]
    env_value = os.environ.get(ENV_PREFIX + env_suffix, "").strip()

    attempts: list[tuple[str, str]] = []
    if env_value:
        attempts.append(("env:" + ENV_PREFIX + env_suffix, env_value))
    attempts.append(("sys.path", module_name))
    for entry in cfg.get("search_paths", []) or []:
        attempts.append(("config:search_paths", entry))

    first_error = ""
    for source, target in attempts:
        try:
            if source.startswith("env:"):
                candidate = Path(target)
                if candidate.is_dir():
                    if str(candidate) not in sys.path:
                        sys.path.insert(0, str(candidate))
                    module = importlib.import_module(module_name)
                else:
                    module = _load_from_file(candidate)
            elif source == "sys.path":
                module = importlib.import_module(module_name)
            else:
                directory = Path(target)
                if not directory.is_dir():
                    continue
                added = str(directory) not in sys.path
                if added:
                    sys.path.insert(0, str(directory))
                try:
                    module = importlib.import_module(module_name)
                finally:
                    if added:
                        try:
                            sys.path.remove(str(directory))
                        except ValueError:
                            pass
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            if not first_error:
                first_error = f"{source}: {type(exc).__name__}: {exc}"
            continue

        missing = tuple(a for a in required if not hasattr(module, a))
        return Resolution(
            capability=capability,
            module_name=module_name,
            source=source,
            detail="" if not missing else f"missing attributes: {', '.join(missing)}",
            module=module,
            missing_attributes=missing,
        )

    return Resolution(
        capability=capability,
        module_name=module_name,
        source="unresolved",
        detail=first_error or f"no provider for {module_name!r}",
    )


def resolve_providers(capabilities: tuple[str, ...] | None = None) -> ProviderSet:
    """Resolve every requested capability and report how each was obtained."""
    cfg = load_config()
    names = capabilities if capabilities is not None else tuple(sorted(REQUIREMENTS))
    return ProviderSet(
        resolutions={name: _resolve_one(name, cfg) for name in names}
    )


def available_capabilities(provider_set: ProviderSet) -> tuple[str, ...]:
    return tuple(
        name for name in sorted(provider_set.resolutions) if provider_set.is_available(name)
    )


def describe(provider_set: ProviderSet) -> Callable[[], str]:
    def _render() -> str:
        lines = ["provider resolution:"]
        for name, res in sorted(provider_set.resolutions.items()):
            mark = "ok " if res.ok else "MISS"
            lines.append(f"  [{mark}] {name:22s} <- {res.source} ({res.module_name})")
            if res.detail:
                lines.append(f"         {res.detail}")
        return "\n".join(lines)

    return _render
