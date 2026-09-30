"""State Registry Implementation.

The registry records decisions; it does not reinterpret them.
Append-only state history. Provenance-referenced. Schema-validated.
Self-governance boundary established: no component may acquire authority
over the mechanism that determines what it is allowed to do.
"""
from __future__ import annotations

import json
import os
import re
import shlex
from datetime import datetime
from pathlib import Path
from typing import Optional

from .registry_schema import (
    ComponentState, Disposition, ResearchState, State, Policy,
    OperationPolicy, OperationLevel, Authority, EffectivePolicy,
    OperationResult, ProvenanceChain, HistoryVerification,
    RegistryCorruptionError, _hash_record, GENESIS_HASH,
)

# Legal state transitions
LEGAL_TRANSITIONS: dict[Disposition, set[Disposition]] = {
    Disposition.OPEN: {Disposition.PRESERVE, Disposition.CLOSED, Disposition.VOIDED},
    Disposition.PRESERVE: {Disposition.CLOSED, Disposition.SUPERSEDED},
    Disposition.CLOSED: {Disposition.OPEN, Disposition.PRESERVE, Disposition.SUPERSEDED},
    Disposition.VOIDED: {Disposition.OPEN, Disposition.SUPERSEDED},
    Disposition.SUPERSEDED: set(),  # terminal state
}

# The registry self-governance component name
REGISTRY_COMPONENT = "STATE_REGISTRY"

#: Root that relative evidence references resolve against.
#:
#: Upstream this was ``<parent of the state_registry package>`` -- i.e. wherever
#: the operator happened to keep the estate. That made evidence resolution depend
#: on an install location, which is exactly the machine coupling this code exists
#: to remove. It now defaults to the repository root and can be pointed anywhere
#: explicitly via ``VERITAS_WORKSPACE_ROOT``.
#:
#: Only *relative* references are resolved against this. Absolute references are
#: used as given, and a reference that does not resolve is recorded as
#: ``exists: False`` rather than being treated as satisfied.
WORKSPACE_ROOT = Path(
    os.environ.get("VERITAS_WORKSPACE_ROOT")
    or Path(__file__).resolve().parent.parent.parent
)
_LINE_ANCHOR = re.compile(r"^(?P<path>.+):(?P<line>[1-9]\d*)$")


def _resolve_artifact_reference(reference: str, repository: str) -> dict:
    """Resolve a file, file:line anchor, or Python command reference.

    Registry evidence is declarative: commands are inspected for their script
    path and are never executed here.
    """
    raw = reference.strip()
    artifact = raw
    kind = "file"

    try:
        tokens = shlex.split(raw, posix=True)
    except ValueError:
        tokens = []

    if tokens and tokens[0].lower() in {"python", "python3", "py"}:
        script = next(
            (token for token in tokens[1:] if not token.startswith("-")),
            "",
        )
        artifact = script
        kind = "command"

    line = None
    anchor = _LINE_ANCHOR.match(artifact)
    if anchor and not (
        len(anchor.group("path")) == 1 and anchor.group("path").isalpha()
    ):
        artifact = anchor.group("path")
        line = int(anchor.group("line"))
        kind = "line_anchor"

    path = Path(artifact) if artifact else Path()
    if artifact and not path.is_absolute():
        if kind == "command" and repository:
            repo_path = Path(repository)
            if not path.parts or path.parts[0].lower() != repo_path.name.lower():
                path = repo_path / path
        path = WORKSPACE_ROOT / path

    exists = bool(artifact) and path.is_file()
    if exists and line is not None:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                exists = sum(1 for _ in handle) >= line
        except OSError:
            exists = False

    return {
        "path": raw,
        "resolved_path": str(path),
        "exists": exists,
        "kind": kind,
        "line": line,
    }


class StateRegistry:
    """Append-only state registry with schema validation and self-governance."""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = str(Path(__file__).parent / "data")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.data_dir / "registry.json"
        self.components: dict[str, ComponentState] = {}
        self._load()

    def _load(self):
        if not self.registry_file.exists():
            return

        try:
            with open(self.registry_file, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            raise RegistryCorruptionError(
                f"Registry file is malformed: {e}"
            )

        # Validate schema
        if "components" not in data:
            raise RegistryCorruptionError(
                "Registry file missing 'components' key"
            )

        # Load and validate each component
        for name, comp_data in data.get("components", {}).items():
            try:
                self.components[name] = ComponentState.from_dict(comp_data)
            except (KeyError, ValueError) as e:
                raise RegistryCorruptionError(
                    f"Component '{name}' has malformed data: {e}"
                )

        # Validate history chains
        for name in self.components:
            verification = self._verify_history(name)
            if not verification.valid:
                raise RegistryCorruptionError(
                    f"Component '{name}' history integrity failed: {verification.error}"
                )

    def _save(self):
        data = {
            "version": 1,
            "last_modified": datetime.now().isoformat(),
            "components": {
                name: comp.to_dict()
                for name, comp in self.components.items()
            },
        }
        with open(self.registry_file, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, component: ComponentState) -> None:
        """Register a new component. Fails if component already exists."""
        if component.name in self.components:
            raise ValueError(
                f"Component '{component.name}' already exists. "
                "Use transition() to change state."
            )

        now = datetime.now().isoformat()
        component.metadata["created_date"] = now
        component.metadata["last_modified"] = now

        # Create genesis record with hash
        genesis = {
            "action": "registered",
            "timestamp": now,
            "state": component.state.disposition.value,
        }
        genesis["prev_hash"] = GENESIS_HASH
        genesis["hash"] = _hash_record(genesis)
        component.history.append(genesis)

        self.components[component.name] = component
        self._save()

    def transition(
        self,
        component_name: str,
        new_disposition: Disposition,
        new_research_state: Optional[ResearchState] = None,
        established_by: str = "",
        provenance: str = "",
        evidence: list[str] = None,
    ) -> None:
        """Transition a component to a new state. Validates legal transitions."""
        if component_name not in self.components:
            raise KeyError(f"Component '{component_name}' not found in registry.")

        comp = self.components[component_name]
        old_disposition = comp.state.disposition

        if new_disposition not in LEGAL_TRANSITIONS.get(old_disposition, set()):
            allowed = LEGAL_TRANSITIONS.get(old_disposition, set())
            allowed_str = ", ".join(s.value for s in allowed) if allowed else "none (terminal)"
            raise ValueError(
                f"Illegal transition: {old_disposition.value} -> {new_disposition.value}. "
                f"Allowed: {allowed_str}"
            )

        now = datetime.now().isoformat()

        # Get predecessor hash
        prev_hash = comp.history[-1]["hash"] if comp.history else GENESIS_HASH

        # Create new history record with hash chain
        record = {
            "action": "transition",
            "from": old_disposition.value,
            "to": new_disposition.value,
            "timestamp": now,
            "established_by": established_by,
            "provenance": provenance,
            "prev_hash": prev_hash,
        }
        record["hash"] = _hash_record(record)
        comp.history.append(record)

        # Update state
        comp.state.disposition = new_disposition
        comp.state.version += 1
        comp.state.established_by = established_by
        comp.state.established_date = now
        if new_research_state is not None:
            comp.state.research_state = new_research_state

        # Update authority
        if provenance:
            comp.authority.provenance = provenance
        if established_by:
            comp.authority.established_by = established_by
        if evidence:
            comp.authority.evidence = evidence

        comp.metadata["last_modified"] = now
        self._save()

    def get(self, component_name: str) -> Optional[ComponentState]:
        """Return full component state."""
        return self.components.get(component_name)

    def can_modify(
        self, component_name: str, operation: str
    ) -> OperationResult:
        """Check if a specific operation is permitted.

        Disposition-level gating:
          OPEN         → all operations ALLOWED (transition opens the surface)
          SUPERSEDED   → all operations BLOCKED (terminal state)
          VOIDED       → all operations BLOCKED (terminal state)
          PRESERVE/CLOSED → consult per-operation policy
        """
        comp = self.components.get(component_name)
        if comp is None:
            return OperationResult(
                permitted=True,
                reason="Component not in registry (unknown != forbidden)",
                required_authority="none",
            )

        # Disposition-level overrides (hard block / hard allow)
        disp = comp.state.disposition
        if disp == Disposition.SUPERSEDED:
            return OperationResult(
                permitted=False,
                reason=f"Component {component_name} is SUPERSEDED (terminal state)",
                required_authority="none -- terminal state",
            )
        if disp == Disposition.VOIDED:
            return OperationResult(
                permitted=False,
                reason=f"Component {component_name} is VOIDED (terminal state)",
                required_authority="none -- terminal state",
            )
        if disp == Disposition.OPEN:
            return OperationResult(
                permitted=True,
                reason=f"Component {component_name} is OPEN: all operations permitted",
                required_authority="none",
            )

        # PRESERVE / CLOSED: consult per-operation policy
        if operation == "new_experiment":
            op_policy = comp.policy.new_experiment
        elif operation == "reopening":
            op_policy = comp.policy.reopening
        else:
            op_policy = comp.policy.get_operation_policy(operation)

        if op_policy.level == OperationLevel.PROHIBITED:
            return OperationResult(
                permitted=False,
                reason=f"Operation '{operation}' is PROHIBITED for {component_name}: {op_policy.reason}",
                required_authority="none -- operation prohibited",
            )

        if op_policy.level == OperationLevel.REQUIRES_AUTHORIZATION:
            return OperationResult(
                permitted=False,
                reason=f"Operation '{operation}' requires authorization for {component_name}: {op_policy.reason}",
                required_authority=comp.authority.requires_for_reopening,
            )

        return OperationResult(
            permitted=True,
            reason=f"Operation '{operation}' is ALLOWED for {component_name}",
            required_authority="none",
        )

    def required_authority(self, component_name: str, operation: str) -> str:
        """Return what authority is needed for an operation."""
        result = self.can_modify(component_name, operation)
        return result.required_authority

    def get_provenance(self, component_name: str) -> Optional[ProvenanceChain]:
        """Return the full provenance chain."""
        comp = self.components.get(component_name)
        if comp is None:
            return None

        chain = []
        if comp.authority.provenance:
            chain.append(comp.authority.provenance)
        chain.extend(comp.authority.evidence)

        return ProvenanceChain(
            component=comp.name,
            state=comp.state.disposition.value,
            document=comp.authority.provenance,
            experiment=comp.state.established_by,
            authority=comp.authority.established_by,
            chain=chain,
        )

    def get_effective_policy(self, component_name: str) -> Optional[EffectivePolicy]:
        """Return the resolved policy."""
        comp = self.components.get(component_name)
        if comp is None:
            return None

        return EffectivePolicy(
            component=comp.name,
            disposition=comp.state.disposition.value,
            research_state=comp.state.research_state.value,
            operations={
                k: v for k, v in comp.policy.modification.items()
            },
            last_verified=comp.metadata.get("last_modified", ""),
            provenance_valid=bool(comp.authority.provenance),
        )

    def list_components(
        self,
        disposition: str = None,
        research_state: str = None,
    ) -> list[ComponentState]:
        """List components filtered by state/disposition."""
        results = []
        for comp in self.components.values():
            if disposition and comp.state.disposition.value != disposition:
                continue
            if research_state and comp.state.research_state.value != research_state:
                continue
            results.append(comp)
        return results

    def verify_provenance(self, component_name: str) -> dict:
        """Check file, line-anchor, and command-script provenance artifacts."""
        comp = self.components.get(component_name)
        if comp is None:
            return {"valid": False, "reason": "component not found"}

        checks = []
        all_valid = True

        prov = comp.authority.provenance
        if prov:
            check = _resolve_artifact_reference(prov, comp.repository)
            checks.append(check)
            if not check["exists"]:
                all_valid = False

        for ev in comp.authority.evidence:
            check = _resolve_artifact_reference(ev, comp.repository)
            checks.append(check)
            if not check["exists"]:
                all_valid = False

        return {
            "valid": all_valid,
            "checks": checks,
            "component": component_name,
        }

    def _verify_history(self, component_name: str) -> HistoryVerification:
        """Verify the hash chain for a single component."""
        comp = self.components.get(component_name)
        if comp is None:
            return HistoryVerification(
                valid=False,
                component=component_name,
                records_checked=0,
                error="component not found",
            )

        history = comp.history
        if not history:
            return HistoryVerification(
                valid=False,
                component=component_name,
                records_checked=0,
                error="empty history",
            )

        for i, record in enumerate(history):
            # Verify hash
            computed_hash = _hash_record(record)
            if record.get("hash") != computed_hash:
                return HistoryVerification(
                    valid=False,
                    component=component_name,
                    records_checked=i,
                    first_invalid_record=i,
                    error=f"record {i}: hash mismatch (expected {computed_hash}, got {record.get('hash')})",
                )

            # Verify chain link
            expected_prev = GENESIS_HASH if i == 0 else history[i - 1]["hash"]
            if record.get("prev_hash") != expected_prev:
                return HistoryVerification(
                    valid=False,
                    component=component_name,
                    records_checked=i,
                    first_invalid_record=i,
                    error=f"record {i}: prev_hash mismatch (expected {expected_prev}, got {record.get('prev_hash')})",
                )

        return HistoryVerification(
            valid=True,
            component=component_name,
            records_checked=len(history),
        )

    def verify_history(self, component_name: str) -> HistoryVerification:
        """Public API: verify the hash chain for a component."""
        return self._verify_history(component_name)

    def verify_all(self) -> dict[str, HistoryVerification]:
        """Verify history chains for all components."""
        return {
            name: self._verify_history(name)
            for name in self.components
        }

    def summary(self) -> str:
        """Human-readable summary of registry state."""
        lines = ["State Registry Summary", "=" * 40]
        for name, comp in sorted(self.components.items()):
            lines.append(
                f"  {name}: {comp.state.disposition.value} / "
                f"{comp.state.research_state.value} "
                f"(v{comp.state.version})"
            )
        lines.append(f"\nTotal: {len(self.components)} components")
        return "\n".join(lines)
