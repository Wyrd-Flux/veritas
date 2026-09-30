"""Veritas session: capability discovery + governed relation admission + provenance.

Veritas exposes four capabilities:

``find``        a need -> qualified candidate leads from a caller-supplied registry
``predicates``  the registered predicate strength lattice
``admit``       before/after relation set -> accept / refuse / admissible-loss verdict
``provenance``  component state transitions -> hash-chained, policy-gated record

The first three delegate to ``wyrd-evidence-core``, an ordinary installed
dependency. The fourth is Veritas' own: capability discovery, which needs a
provider model the evidence core has no business knowing about.

Every refusal reason is the upstream module's own. Veritas adds no opinions.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from wyrd_evidence_core import outcome_taxonomy
from wyrd_evidence_core import predicate_semantics as _predicates
from wyrd_evidence_core import registry as _registry
from wyrd_evidence_core import registry_schema as _schema
from wyrd_evidence_core import writeback_validator as _writeback

from .capabilities import (
    CapabilityRegistryProvider,
    LocalJsonRegistryProvider,
    load_registries,
    search,
)

VERITAS_VERSION = "0.2.0"

#: Capabilities supplied by wyrd-evidence-core. Resolved at import time from an
#: installed dependency, so there is nothing here that can fail to load.
EVIDENCE_CORE_CAPABILITIES = (
    "predicate_semantics",
    "writeback_validator",
    "outcome_taxonomy",
    "registry",
)


class CapabilityStatus(str, Enum):
    """Availability of one capability in this session."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"

    def as_dict(self) -> dict[str, str]:
        return {"status": self.value}


class EdgeVerdict(str, Enum):
    """Outcome of an edge admission request."""

    ADMITTED = "ADMITTED"
    REFUSED = "REFUSED"
    ADMITTED_WITH_LOSS = "ADMITTED_WITH_LOSS"
    UNAVAILABLE = "UNAVAILABLE"

    def as_dict(self) -> dict[str, str]:
        return {"verdict": self.value}


@dataclass
class LoadReport:
    """Why each capability did or did not resolve."""

    statuses: dict[str, CapabilityStatus] = field(default_factory=dict)
    resolutions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def status(self, capability: str) -> CapabilityStatus:
        return self.statuses.get(capability, CapabilityStatus.UNAVAILABLE)

    @property
    def complete(self) -> bool:
        return all(s is CapabilityStatus.AVAILABLE for s in self.statuses.values())

    def missing(self) -> tuple[str, ...]:
        return tuple(
            sorted(n for n, s in self.statuses.items() if s is not CapabilityStatus.UNAVAILABLE)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "veritas_version": VERITAS_VERSION,
            "complete": self.complete,
            "statuses": {n: s.value for n, s in sorted(self.statuses.items())},
            "resolutions": {n: self.resolutions[n] for n in sorted(self.resolutions)},
        }

    def render(self) -> str:
        lines = ["Veritas evidence capabilities"]
        for name, status in sorted(self.statuses.items()):
            res = self.resolutions.get(name, {})
            mark = "ok  " if status is CapabilityStatus.AVAILABLE else "MISS"
            lines.append(f"  [{mark}] {name:22s} {status.value}")
            if res.get("detail"):
                lines.append(f"         {res['detail']}")
        lines.append(f"  complete: {self.complete}")
        return "\n".join(lines)


class VeritasSession:
    """The evidence primitives plus Veritas' own capability-discovery operations."""

    def __init__(
        self,
        providers: Sequence[CapabilityRegistryProvider] | None = None,
    ) -> None:
        self._providers = list(providers) if providers is not None else []
        self.load = LoadReport(
            statuses={
                name: CapabilityStatus.AVAILABLE
                for name in EVIDENCE_CORE_CAPABILITIES
            },
            resolutions={
                name: {"detail": f"wyrd-evidence-core  ({name})"}
                for name in EVIDENCE_CORE_CAPABILITIES
            },
        )

    # -- capability discovery ---------------------------------------------- #

    @property
    def providers(self) -> list[CapabilityRegistryProvider]:
        return list(self._providers)

    def use_registry(self, path: str | Path) -> None:
        """Point ``find`` at a caller-supplied registry, replacing the default."""
        self._providers = [LocalJsonRegistryProvider(Path(path))]

    def find_capability(self, request: str) -> dict[str, Any]:
        """Search the configured registries for candidate leads.

        A lead is a lexical near-match, not a capability identity and not a
        recommendation. An unreadable registry raises rather than returning an
        answer, so a mistyped path cannot look like a genuine gap.
        """
        if not self._providers:
            self._providers = load_registries()
        result = search(request, self._providers)
        result["capability"] = CapabilityStatus.AVAILABLE.value
        return result

    # -- predicate lattice ------------------------------------------------- #

    def predicate_lattice(self) -> dict[str, Any]:
        """The registered predicates with their strength class and powers."""
        module = _predicates
        rows = []
        for name, predicate in sorted(module.PREDICATES.items()):
            rows.append(
                {
                    "predicate": name,
                    "strength": predicate.strength_class,
                    "strength_name": module.STRENGTH_NAME.get(
                        predicate.strength_class, str(predicate.strength_class)
                    ),
                    "directional": bool(predicate.directional),
                    "implies_causation": bool(predicate.implies_causation),
                    "may_establish_identity": bool(predicate.may_establish_identity),
                    "may_establish_ownership": bool(predicate.may_establish_ownership),
                    "why": predicate.why,
                }
            )
        return {
            "capability": self.load.status("predicate_semantics").value,
            "predicate_count": len(rows),
            "self_check_failures": len(module.self_check() or []),
            "strength_classes": dict(module.STRENGTH_NAME),
            "predicates": rows,
        }

    # -- edge admission ---------------------------------------------------- #

    def parse_edges(self, rows: Sequence[dict[str, Any]]) -> tuple[Any, ...]:
        """Build ``Edge`` objects from plain dicts."""
        return tuple(_writeback.Edge(**row) for row in rows)

    def admit_edges(
        self,
        before: Sequence[dict[str, Any]],
        proposed: Sequence[dict[str, Any]],
        authorization: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Admit a proposed edge set against the current one.

        ``before``/``proposed`` rows are dicts accepted by the upstream
        ``Edge`` dataclass: ``subject``, ``predicate``, ``obj``, and optionally
        ``basis``, ``evidence``, ``subject_time``, ``object_time``.
        """
        module = _writeback
        prior = list(self.parse_edges(before))
        incoming = list(self.parse_edges(proposed))
        verdict = module.validate(
            prior, incoming, authorization=tuple(authorization)
        )
        return {
            "verdict": (
                EdgeVerdict.REFUSED.value
                if verdict.refused
                else (
                    EdgeVerdict.ADMITTED_WITH_LOSS.value
                    if verdict.admissible_losses
                    else EdgeVerdict.ADMITTED.value
                )
            ),
            "capability": self.load.status("writeback_validator").value,
            "accepted": [str(e) for e in verdict.accepted],
            "refused": [
                {"edge": f.edge, "code": f.code, "detail": f.detail}
                for f in verdict.refused
            ],
            "admissible_losses": [
                {"edge": f.edge, "code": f.code, "detail": f.detail}
                for f in verdict.admissible_losses
            ],
            "summary": verdict.summary(),
        }

    # -- outcome taxonomy -------------------------------------------------- #

    def outcome_classes(self) -> dict[str, Any]:
        module = outcome_taxonomy
        return {
            "capability": self.load.status("outcome_taxonomy").value,
            "classes": [getattr(c, "value", str(c)) for c in module.ALL_CLASSES],
            "resolved": [getattr(c, "value", str(c)) for c in module.RESOLVED_CLASSES],
            "refused": [getattr(c, "value", str(c)) for c in module.REFUSED_CLASSES],
            "open": [getattr(c, "value", str(c)) for c in module.OPEN_CLASSES],
            "self_check_failures": len(module.selfcheck() or []),
        }

    def classify_outcome(self, counts: dict[str, int]) -> dict[str, Any]:
        module = outcome_taxonomy
        return {
            "capability": self.load.status("outcome_taxonomy").value,
            "counts": dict(counts),
            "render": module.render(module.summarise(counts)),
        }

    # -- provenance -------------------------------------------------------- #

    def open_registry(self, data_dir: str | Path | None = None) -> Any:
        """Open a ``StateRegistry``.

        ``data_dir`` defaults to a fresh temporary directory so a demo run never
        writes into an existing registry corpus.
        """
        module = _registry
        target = Path(data_dir) if data_dir is not None else Path(
            tempfile.mkdtemp(prefix="veritas_registry_")
        )
        return module.StateRegistry(data_dir=str(target))

    def register_component(
        self,
        registry: Any,
        *,
        name: str,
        repository: str,
        path: str,
        disposition: str = "OPEN",
        research_state: str = "ACTIVE",
        established_by: str = "veritas-demo",
        established_date: str = "",
        reopening_level: str = "REQUIRES_AUTHORIZATION",
        reopening_reason: str = "reopening requires explicit authorization",
    ) -> Any:
        """Register a component using the evidence core's schema types."""
        schema = _schema
        component = schema.ComponentState(
            name=name,
            repository=repository,
            path=path,
            state=schema.State(
                disposition=schema.Disposition(disposition),
                research_state=schema.ResearchState(research_state),
                established_by=established_by,
                established_date=established_date,
                version=1,
            ),
            policy=schema.Policy(
                modification={},
                new_experiment=schema.OperationPolicy(
                    level=schema.OperationLevel.ALLOWED
                ),
                reopening=schema.OperationPolicy(
                    level=schema.OperationLevel(reopening_level), reason=reopening_reason
                ),
            ),
            authority=schema.Authority(
                established_by=established_by,
                provenance="registered by veritas-demo",
                evidence=[],
                requires_for_reopening="Human authorization",
            ),
            dependencies=[],
            metadata={"registered_by": "veritas-demo"},
            history=[],
        )
        registry.register(component)
        return component

    def policy_gate(
        self,
        registry: Any,
        component: str,
        operation: str,
    ) -> dict[str, Any]:
        """Ask the registry whether an operation is permitted."""
        result = registry.can_modify(component, operation)
        return {
            "component": component,
            "operation": operation,
            "permitted": bool(result.permitted),
            "reason": result.reason,
            "required_authority": result.required_authority,
        }

    def verify_provenance(self, registry: Any, component: str) -> dict[str, Any]:
        verification = registry.verify_history(component)
        return {
            "component": component,
            "chain_valid": bool(verification.valid),
            "records_checked": verification.records_checked,
            "first_invalid_record": verification.first_invalid_record,
            "error": verification.error,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def to_json(payload: Any) -> str:
    return json.dumps(_jsonable(payload), indent=2, sort_keys=True)
