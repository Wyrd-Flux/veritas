"""State Registry Schema.

The registry records decisions; it does not reinterpret them.
Every field maps directly to a frozen design document or experiment result.
"""
from __future__ import annotations

import hashlib
import json
import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class Disposition(str, enum.Enum):
    OPEN = "OPEN"
    PRESERVE = "PRESERVE"
    CLOSED = "CLOSED"
    VOIDED = "VOIDED"
    SUPERSEDED = "SUPERSEDED"


class ResearchState(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INCONCLUSIVE = "INCONCLUSIVE"
    H0 = "H0"
    H1 = "H1"
    UNKNOWN = "UNKNOWN"


class OperationLevel(str, enum.Enum):
    ALLOWED = "ALLOWED"
    REQUIRES_AUTHORIZATION = "REQUIRES_AUTHORIZATION"
    PROHIBITED = "PROHIBITED"


GENESIS_HASH = "0" * 64


def _hash_record(record: dict) -> str:
    """SHA-256 of the record content, excluding 'hash' and 'prev_hash'."""
    content = {k: v for k, v in record.items() if k not in ("hash", "prev_hash")}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class OperationPolicy:
    level: OperationLevel
    reason: str = ""


@dataclass
class Policy:
    modification: dict[str, OperationPolicy] = field(default_factory=dict)
    new_experiment: OperationPolicy = field(
        default_factory=lambda: OperationPolicy(OperationLevel.ALLOWED)
    )
    reopening: OperationPolicy = field(
        default_factory=lambda: OperationPolicy(OperationLevel.REQUIRES_AUTHORIZATION)
    )

    def get_operation_policy(self, operation: str) -> OperationPolicy:
        return self.modification.get(
            operation,
            OperationPolicy(OperationLevel.ALLOWED, "default: allowed"),
        )


@dataclass
class Authority:
    established_by: str = ""
    provenance: str = ""
    evidence: list[str] = field(default_factory=list)
    requires_for_reopening: str = "Human authorization"


@dataclass
class ProvenanceChain:
    component: str = ""
    state: str = ""
    document: str = ""
    experiment: str = ""
    result_file: str = ""
    authority: str = ""
    chain: list[str] = field(default_factory=list)


@dataclass
class State:
    disposition: Disposition = Disposition.OPEN
    research_state: ResearchState = ResearchState.UNKNOWN
    established_by: str = ""
    established_date: str = ""
    version: int = 1


@dataclass
class ComponentState:
    name: str = ""
    repository: str = ""
    path: str = ""
    state: State = field(default_factory=State)
    policy: Policy = field(default_factory=Policy)
    authority: Authority = field(default_factory=Authority)
    dependencies: dict = field(default_factory=lambda: {"affects": [], "depends_on": []})
    metadata: dict = field(default_factory=lambda: {
        "created_date": "",
        "last_modified": "",
        "last_modified_by": "",
        "description": "",
    })
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repository": self.repository,
            "path": self.path,
            "state": {
                "disposition": self.state.disposition.value,
                "research_state": self.state.research_state.value,
                "established_by": self.state.established_by,
                "established_date": self.state.established_date,
                "version": self.state.version,
            },
            "policy": {
                "modification": {
                    k: {"level": v.level.value, "reason": v.reason}
                    for k, v in self.policy.modification.items()
                },
                "new_experiment": {
                    "level": self.policy.new_experiment.level.value,
                    "reason": self.policy.new_experiment.reason,
                },
                "reopening": {
                    "level": self.policy.reopening.level.value,
                    "reason": self.policy.reopening.reason,
                },
            },
            "authority": {
                "established_by": self.authority.established_by,
                "provenance": self.authority.provenance,
                "evidence": self.authority.evidence,
                "requires_for_reopening": self.authority.requires_for_reopening,
            },
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ComponentState:
        mod = {}
        for k, v in d.get("policy", {}).get("modification", {}).items():
            mod[k] = OperationPolicy(
                level=OperationLevel(v["level"]),
                reason=v.get("reason", ""),
            )
        policy = Policy(
            modification=mod,
            new_experiment=OperationPolicy(
                level=OperationLevel(d["policy"]["new_experiment"]["level"]),
                reason=d["policy"]["new_experiment"].get("reason", ""),
            ),
            reopening=OperationPolicy(
                level=OperationLevel(d["policy"]["reopening"]["level"]),
                reason=d["policy"]["reopening"].get("reason", ""),
            ),
        )
        return cls(
            name=d["name"],
            repository=d.get("repository", ""),
            path=d.get("path", ""),
            state=State(
                disposition=Disposition(d["state"]["disposition"]),
                research_state=ResearchState(d["state"]["research_state"]),
                established_by=d["state"].get("established_by", ""),
                established_date=d["state"].get("established_date", ""),
                version=d["state"].get("version", 1),
            ),
            policy=policy,
            authority=Authority(
                established_by=d["authority"].get("established_by", ""),
                provenance=d["authority"].get("provenance", ""),
                evidence=d["authority"].get("evidence", []),
                requires_for_reopening=d["authority"].get("requires_for_reopening", ""),
            ),
            dependencies=d.get("dependencies", {"affects": [], "depends_on": []}),
            metadata=d.get("metadata", {}),
            history=d.get("history", []),
        )


@dataclass
class EffectivePolicy:
    component: str
    disposition: str
    research_state: str
    operations: dict[str, OperationPolicy]
    last_verified: str
    provenance_valid: bool


@dataclass
class OperationResult:
    permitted: bool
    reason: str
    required_authority: str
    effective_policy: Optional[EffectivePolicy] = None


@dataclass
class HistoryVerification:
    valid: bool
    component: str
    records_checked: int
    first_invalid_record: Optional[int] = None
    error: Optional[str] = None


class RegistryCorruptionError(Exception):
    """Raised when registry fails schema or history validation."""
    pass


class GovernanceViolation(Exception):
    """Raised when a PROHIBITED operation is attempted in blocking mode."""
    pass
