"""Veritas: governed claim admission, with capability discovery over your registries.

Self-contained: the evidence primitives -- predicate semantics, relation-set
writeback validation, the outcome taxonomy, and the component registry -- are
folded into :mod:`veritas_demo.evidence`. Veritas adds no reimplementation of any
governed behaviour and no opinions about any refusal.

There are no dependencies to install. A clone is runnable on its own.

Capability discovery is Veritas' own, because it needs a provider model: a
registry is whatever the caller supplies, not a corpus baked into the package.
"""

from .capabilities import (
    CapabilityRecord,
    CapabilityRegistryProvider,
    LocalJsonRegistryProvider,
    RegistryUnavailable,
)
from .core import (
    CapabilityStatus,
    EdgeVerdict,
    LoadReport,
    VeritasSession,
    VERITAS_VERSION,
)

__all__ = [
    "CapabilityRecord",
    "CapabilityRegistryProvider",
    "CapabilityStatus",
    "EdgeVerdict",
    "LocalJsonRegistryProvider",
    "LoadReport",
    "RegistryUnavailable",
    "VeritasSession",
    "VERITAS_VERSION",
]
