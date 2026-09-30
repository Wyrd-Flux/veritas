"""Explicit exit-code contract, one per subcommand.

Two independent dimensions are kept apart, because conflating them is a real
defect in either direction:

**Command execution status** -- did Veritas successfully perform the requested
evaluation? This is what the process exit code reports.

**Domain verdict** -- what did the upstream capability decide? This is data in
the output and never influences the exit code, *except* where the domain
answer is itself the absence of an answer.

The two failure modes this exists to prevent:

  * an unavailable capability printing ``UNAVAILABLE`` and exiting 0 -- an
    absent gate reading as a passing gate;
  * a successful evaluation whose governed result happens to be ``REFUSED``
    exiting nonzero -- a valid refusal read as a program failure.

A governed refusal is a successful evaluation. ``selftest`` is the one command
whose domain answer *is* its exit condition, because it asserts expected
behavior rather than reporting it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

#: Process exit codes. Kept small and stable so scripts can branch on them.
EXIT_OK = 0
EXIT_CAPABILITY_UNAVAILABLE = 2
EXIT_ASSERTION_FAILED = 3
EXIT_BAD_INVOCATION = 64


@dataclass(frozen=True)
class ExitContract:
    """Documented exit behaviour for one subcommand."""

    command: str
    required_capability: str | None
    success: str
    failure: str
    notes: str = ""

    def render(self) -> str:
        lines = [
            f"{self.command}",
            f"    capability : {self.required_capability or '(none)'}",
            f"    exit 0 when: {self.success}",
            f"    exit != 0  : {self.failure}",
        ]
        if self.notes:
            lines.append(f"    note       : {self.notes}")
        return "\n".join(lines)


CONTRACTS: dict[str, ExitContract] = {
    "doctor": ExitContract(
        command="doctor",
        required_capability=None,
        success="the evidence capabilities resolved and every configured registry is readable",
        failure="a capability is unresolved, or a configured registry is unreadable",
        notes="also reports which registries 'find' would search",
    ),
    "find": ExitContract(
        command="find",
        required_capability="capability_registry",
        success="the query executed against the configured registries",
        failure="a configured registry could not be read (REGISTRY_UNAVAILABLE)",
        notes=(
            "NO_MATCH, PARTIAL_MATCH and MULTIPLE_CANDIDATES are domain verdicts "
            "and exit 0. They describe the registries searched, not the world; "
            "NO_MATCH is not evidence of absence and must not be flattened into "
            "it. An unreadable registry is a failure to answer and exits "
            "non-zero -- it never falls back to another registry"
        ),
    ),
    "predicates": ExitContract(
        command="predicates",
        required_capability="predicate_semantics",
        success="the lattice loaded and rendered",
        failure="unavailable",
        notes="a predicate's strength class is data, not an exit condition",
    ),
    "outcomes": ExitContract(
        command="outcomes",
        required_capability="outcome_taxonomy",
        success="the taxonomy loaded and rendered",
        failure="unavailable",
        notes="REFUSED_* classes are part of the vocabulary, not failures",
    ),
    "admit": ExitContract(
        command="admit",
        required_capability="writeback_validator",
        success=(
            "the validator ran and the scenario was evaluated -- including a "
            "legitimate REFUSED result"
        ),
        failure="the validator is unavailable",
        notes=(
            "REFUSED, ADMITTED and ADMITTED_WITH_LOSS are all successful "
            "evaluations. An unavailable gate is not a passing gate"
        ),
    ),
    "provenance": ExitContract(
        command="provenance",
        required_capability="registry",
        success="the requested check executed",
        failure="unavailable",
        notes=(
            "a policy refusal -- gate permitted=false, or a component in a "
            "terminal disposition -- is a successful evaluation and exits 0"
        ),
    ),
    "selftest": ExitContract(
        command="selftest",
        required_capability="writeback_validator",
        success="every expected behavioral assertion held",
        failure="an assertion did not hold",
        notes=(
            "the one command whose domain result IS its exit condition: it "
            "asserts expected behavior rather than reporting it"
        ),
    ),
}

EXIT_MEANINGS: dict[int, str] = {
    EXIT_OK: "the requested evaluation completed",
    EXIT_CAPABILITY_UNAVAILABLE: "a required upstream capability was unavailable",
    EXIT_ASSERTION_FAILED: "an expected behavioral assertion did not hold",
    EXIT_BAD_INVOCATION: "the invocation was malformed",
}


def unavailable(capability: str, detail: str = "") -> dict[str, Any]:
    """The standard payload for a command that could not reach its capability."""
    return {
        "capability": "UNAVAILABLE",
        "missing_capability": capability,
        "detail": detail,
        "evaluated": False,
        "exit_code": EXIT_CAPABILITY_UNAVAILABLE,
    }


def from_payload(payload: dict[str, Any], required: str | None) -> int:
    """Derive an exit code from a command payload.

    Reads the execution-status fields only. It never reads a domain verdict
    such as ``REFUSED``, ``ADMITTED``, ``NO_MATCH`` or ``PARTIAL_MATCH``.
    """
    if payload.get("evaluated") is False:
        return int(payload.get("exit_code") or EXIT_CAPABILITY_UNAVAILABLE)
    if payload.get("capability") == "UNAVAILABLE":
        return EXIT_CAPABILITY_UNAVAILABLE
    if required and payload.get("missing_capability") == required:
        return EXIT_CAPABILITY_UNAVAILABLE
    return EXIT_OK


def render_contracts() -> str:
    """The full contract table, for `veritas-demo --help` and documentation."""
    blocks = ["exit-code contract:"]
    for name in sorted(CONTRACTS):
        blocks.append("")
        blocks.append(CONTRACTS[name].render())
    blocks.append("")
    blocks.append("exit codes:")
    for code in sorted(EXIT_MEANINGS):
        blocks.append(f"  {code:>3d}  {EXIT_MEANINGS[code]}")
    blocks.append("")
    blocks.append(
        "command execution status is separate from domain verdict: a governed "
        "REFUSED is a successful evaluation and exits 0"
    )
    return "\n".join(blocks)


def contract_for(command: str) -> ExitContract | None:
    return CONTRACTS.get(command)


def verify_contract(command: str, exit_code: int) -> list[str]:
    """Return violations of the declared contract for an observed exit code.

    Used by the test suite to assert the contract is actually what the code
    says it is, rather than restating the implementation.
    """
    problems: list[str] = []
    contract = CONTRACTS.get(command)
    if contract is None:
        return [f"no exit contract declared for {command!r}"]
    if exit_code == EXIT_OK and contract.failure.startswith("a required upstream"):
        problems.append(
            f"{command}: exited 0 although its contract requires capability "
            f"{contract.required_capability}"
        )
    if exit_code == EXIT_CAPABILITY_UNAVAILABLE and contract.required_capability is None:
        problems.append(
            f"{command}: reported capability-unavailable but declares no required capability"
        )
    if exit_code not in EXIT_MEANINGS:
        problems.append(f"{command}: undocumented exit code {exit_code}")
    return problems


def declared_capabilities() -> Sequence[str]:
    return tuple(
        sorted({c.required_capability for c in CONTRACTS.values() if c.required_capability})
    )
