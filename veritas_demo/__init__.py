"""Adapter layer binding Veritas to the upstream capability implementations.

This package contains **no** reimplementation of any governed behaviour. Every
decision-producing function here delegates to an upstream module loaded through
a provider. If a provider is unavailable the corresponding capability reports
``UNAVAILABLE`` rather than substituting a local approximation.
"""

from .core import (
    CapabilityStatus,
    EdgeVerdict,
    LoadReport,
    VeritasSession,
    VERITAS_VERSION,
)

__all__ = [
    "CapabilityStatus",
    "EdgeVerdict",
    "LoadReport",
    "VeritasSession",
    "VERITAS_VERSION",
]
