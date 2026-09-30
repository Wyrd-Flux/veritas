"""Conformance tests for the Veritas adapter layer.

These tests assert that the adapter **delegates** correctly and that the
upstream engines refuse for the reasons they document. They do not assert the
upstream engines' internal behaviour, which is covered by their own suites
(317 tests for state_registry, self-check suites for the G1 policy modules).

When a capability is unavailable the corresponding tests skip rather than
re-implement the behaviour locally.
"""

from __future__ import annotations

import json

import pytest

from veritas_demo import VERITAS_VERSION
from veritas_demo.cli import SCENARIOS, main
from veritas_demo.core import (
    CapabilityStatus,
    EdgeVerdict,
    LoadReport,
    VeritasSession,
    to_json,
)
from veritas_demo.exit_codes import (
    CONTRACTS,
    EXIT_ASSERTION_FAILED,
    EXIT_BAD_INVOCATION,
    EXIT_CAPABILITY_UNAVAILABLE,
    EXIT_MEANINGS,
    EXIT_OK,
    declared_capabilities,
    from_payload,
    render_contracts,
    verify_contract,
)
from veritas_demo.providers import (
    CapabilityUnavailable,
    REQUIREMENTS,
    resolve_providers,
)

REQUIRED_FOR_FULL_RUN = (
    "registry",
    "predicate_semantics",
    "writeback_validator",
    "outcome_taxonomy",
)


def _stub_session(*unavailable: str) -> VeritasSession:
    """A session where the named capabilities did not resolve.

    This is the important negative path: a missing capability must degrade to a
    reported UNAVAILABLE, never to a locally substituted answer.
    """
    from veritas_demo.providers import ProviderSet

    stub = VeritasSession.__new__(VeritasSession)
    stub._providers = ProviderSet()
    report = LoadReport()
    for name in unavailable:
        report.statuses[name] = CapabilityStatus.UNAVAILABLE
        report.resolutions[name] = {
            "capability": name,
            "module": name,
            "source": "unresolved",
            "detail": "stubbed for test",
            "resolved": False,
            "missing_attributes": [],
        }
    stub.load = report
    return stub


@pytest.fixture(scope="session")
def session() -> VeritasSession:
    return VeritasSession()


def _requires(session: VeritasSession, *capabilities: str) -> None:
    missing = [
        name
        for name in capabilities
        if session.load.status(name) is not CapabilityStatus.AVAILABLE
    ]
    if missing:
        pytest.skip(f"upstream capability unavailable: {', '.join(missing)}")


# --------------------------------------------------------------------------- #
# adapter / loading
# --------------------------------------------------------------------------- #


def test_package_exposes_version() -> None:
    assert VERITAS_VERSION == "0.1.0"


def test_every_declared_capability_is_attempted(session: VeritasSession) -> None:
    assert set(session.load.statuses) == set(REQUIREMENTS)


def test_resolution_reports_its_source(session: VeritasSession) -> None:
    report = session.load.as_dict()
    assert set(report["statuses"]) == set(REQUIREMENTS)
    for resolution in report["resolutions"].values():
        assert resolution["source"], "every resolution must name how it was obtained"
        assert "module" in resolution


def test_unresolved_capability_is_not_substituted() -> None:
    providers = resolve_providers(capabilities=("registry",))
    # A capability that was never resolved must not report as available, and
    # must not raise something other than the declared error.
    assert not providers.is_available("capability_that_was_not_requested")
    with pytest.raises(CapabilityUnavailable):
        providers.require("capability_that_was_not_requested")


def test_json_render_is_serialisable(session: VeritasSession) -> None:
    payload = json.loads(to_json(session.load.as_dict()))
    assert payload["veritas_version"] == VERITAS_VERSION


# --------------------------------------------------------------------------- #
# capability discovery
# --------------------------------------------------------------------------- #


def test_find_returns_a_verdict_for_any_query(session: VeritasSession) -> None:
    _requires(session, "capability_inventory")
    result = session.find_capability("evidence verification")
    assert result["verdict"]
    assert "candidates" in result


def test_find_on_absent_capability_is_not_an_error(session: VeritasSession) -> None:
    _requires(session, "capability_inventory")
    result = session.find_capability("brew coffee on a lark")
    assert result["verdict"] in {
        "NO_MATCH",
        "PARTIAL_MATCH",
        "MULTIPLE_CANDIDATES",
        "REGISTERED_BUT_NOT_CALLABLE",
        "IMPLEMENTED_BUT_UNBOUND",
        "CAPABILITY_UNVERIFIED",
    }


def test_find_reports_unavailable_rather_than_guessing() -> None:
    result = _stub_session("capability_inventory").find_capability("anything")
    assert result["verdict"] == CapabilityStatus.UNAVAILABLE.value


# --------------------------------------------------------------------------- #
# predicate lattice
# --------------------------------------------------------------------------- #


def test_predicate_lattice_exposes_strength_and_powers(session: VeritasSession) -> None:
    _requires(session, "predicate_semantics")
    lattice = session.predicate_lattice()
    assert lattice["predicate_count"] >= 20
    assert lattice["self_check_failures"] == 0
    names = {row["predicate"] for row in lattice["predicates"]}
    assert {"CAUSES", "ASSOCIATED_WITH", "OWNED_BY_OPERATOR"} <= names


def test_authority_predicates_are_the_only_ownership_granting_ones(
    session: VeritasSession,
) -> None:
    _requires(session, "predicate_semantics")
    lattice = session.predicate_lattice()
    granting = [
        row["predicate"] for row in lattice["predicates"] if row["may_establish_ownership"]
    ]
    assert set(granting) == {"OWNED_BY_CONCEPT", "OWNED_BY_OPERATOR"}


def test_causal_predicates_are_the_only_causation_implying_ones(
    session: VeritasSession,
) -> None:
    _requires(session, "predicate_semantics")
    lattice = session.predicate_lattice()
    implying = [
        row["predicate"] for row in lattice["predicates"] if row["implies_causation"]
    ]
    assert set(implying) == {"CAUSES", "MOTIVATES", "RESOLVES"}


# --------------------------------------------------------------------------- #
# edge admission
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("legitimate", EdgeVerdict.ADMITTED.value),
        ("inflate-correlation", EdgeVerdict.REFUSED.value),
        ("escalate-identity", EdgeVerdict.REFUSED.value),
        ("escalate-ownership", EdgeVerdict.REFUSED.value),
        ("invent-predicate", EdgeVerdict.REFUSED.value),
        ("weakening-loss", EdgeVerdict.ADMITTED_WITH_LOSS.value),
    ],
)
def test_admission_verdicts(session: VeritasSession, scenario: str, expected: str) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS[scenario]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert result["verdict"] == expected


def test_correlation_to_causation_is_refused_with_its_named_reason(
    session: VeritasSession,
) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS["inflate-correlation"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    codes = {f["code"] for f in result["refused"]}
    assert "CAUSATION_FROM_CORRELATION" in codes


def test_path_to_concept_identity_is_refused(session: VeritasSession) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS["escalate-identity"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert "IDENTITY_ESCALATION" in {f["code"] for f in result["refused"]}


def test_path_ownership_is_refused(session: VeritasSession) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS["escalate-ownership"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert "OWNERSHIP_ESCALATION" in {f["code"] for f in result["refused"]}


def test_unregistered_predicate_is_refused(session: VeritasSession) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS["invent-predicate"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert "UNREGISTERED_PREDICATE" in {f["code"] for f in result["refused"]}


def test_weakening_is_recorded_as_a_loss_not_a_refusal(session: VeritasSession) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS["weakening-loss"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert result["refused"] == []
    assert result["admissible_losses"], "a downgrade must be recorded, not silently accepted"


def test_admission_is_deterministic(session: VeritasSession) -> None:
    _requires(session, "writeback_validator")
    spec = SCENARIOS["inflate-correlation"]
    first = session.admit_edges(spec["before"], spec["proposed"])
    second = session.admit_edges(spec["before"], spec["proposed"])
    assert to_json(first) == to_json(second)


def test_unavailable_validator_does_not_approve() -> None:
    result = _stub_session("writeback_validator").admit_edges(
        [], [{"subject": "a", "predicate": "CAUSES", "obj": "b"}]
    )
    assert result["verdict"] == EdgeVerdict.UNAVAILABLE.value


def test_unavailable_capabilities_report_rather_than_raise() -> None:
    stub = _stub_session("predicate_semantics", "outcome_taxonomy")
    assert stub.predicate_lattice()["capability"] == CapabilityStatus.UNAVAILABLE.value
    assert stub.outcome_classes()["capability"] == CapabilityStatus.UNAVAILABLE.value


# --------------------------------------------------------------------------- #
# outcome taxonomy
# --------------------------------------------------------------------------- #


def test_outcome_vocabulary_partitions_into_families(session: VeritasSession) -> None:
    _requires(session, "outcome_taxonomy")
    data = session.outcome_classes()
    assert data["self_check_failures"] == 0
    resolved = set(data["resolved"])
    refused = set(data["refused"])
    open_ = set(data["open"])
    assert resolved and refused and open_
    assert not (resolved & refused), "a class cannot be both resolved and refused"
    assert not (resolved & open_)
    assert not (refused & open_)


# --------------------------------------------------------------------------- #
# provenance / policy gate
# --------------------------------------------------------------------------- #


def test_registration_creates_a_valid_chain(session: VeritasSession) -> None:
    _requires(session, "registry")
    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    verification = session.verify_provenance(registry, "ROUTER")
    assert verification["chain_valid"] is True
    assert verification["records_checked"] >= 1


def test_open_component_permits_operation(session: VeritasSession) -> None:
    _requires(session, "registry")
    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    gate = session.policy_gate(registry, "ROUTER", "implementation")
    assert gate["permitted"] is True


def test_terminal_disposition_blocks_operation(session: VeritasSession) -> None:
    _requires(session, "registry")
    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    schema = __import__("state_registry.schema", fromlist=["Disposition"])
    registry.transition(
        "ROUTER", schema.Disposition.PRESERVE, established_by="test", evidence=["e"]
    )
    registry.transition(
        "ROUTER", schema.Disposition.SUPERSEDED, established_by="test", evidence=["e"]
    )
    gate = session.policy_gate(registry, "ROUTER", "implementation")
    assert gate["permitted"] is False
    assert "SUPERSEDED" in gate["reason"]


def test_chain_verification_detects_tampering(session: VeritasSession) -> None:
    _requires(session, "registry")
    import json as _json
    from pathlib import Path

    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    schema = __import__("state_registry.schema", fromlist=["Disposition"])
    registry.transition(
        "ROUTER", schema.Disposition.CLOSED, established_by="test", evidence=["e"]
    )
    verification = session.verify_provenance(registry, "ROUTER")
    assert verification["chain_valid"] is True
    assert verification["records_checked"] >= 2

    path = Path(registry.registry_file)
    payload = _json.loads(path.read_text(encoding="utf8"))
    payload["components"]["ROUTER"]["history"][1]["action"] = "forged"
    path.write_text(_json.dumps(payload), encoding="utf8")

    from state_registry.schema import RegistryCorruptionError

    with pytest.raises(RegistryCorruptionError):
        session.open_registry(path.parent)


def test_unknown_component_is_permitted_not_forbidden(session: VeritasSession) -> None:
    _requires(session, "registry")
    registry = session.open_registry()
    gate = session.policy_gate(registry, "NEVER_REGISTERED", "implementation")
    assert gate["permitted"] is True
    assert "unknown != forbidden" in gate["reason"]


def test_open_registry_defaults_to_a_throwaway_directory(session: VeritasSession) -> None:
    _requires(session, "registry")
    from pathlib import Path

    registry = session.open_registry()
    directory = Path(registry.registry_file).parent
    assert directory.exists()
    assert "veritas_registry_" in directory.name


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0


def test_cli_doctor_exits_nonzero_when_incomplete(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    code = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert "complete" in payload
    assert code == (EXIT_OK if payload["complete"] else EXIT_CAPABILITY_UNAVAILABLE)


def test_cli_selftest(capsys: pytest.CaptureFixture[str], session: VeritasSession) -> None:
    missing = [
        name
        for name in REQUIRED_FOR_FULL_RUN
        if session.load.status(name) is not CapabilityStatus.AVAILABLE
    ]
    if missing:
        pytest.skip(f"upstream capability unavailable: {', '.join(missing)}")
    code = main(["selftest"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["passed"] is True
    assert all(row["pass"] for row in payload["results"])


def test_cli_selftest_text_rendering(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    missing = [
        name
        for name in ("writeback_validator",)
        if session.load.status(name) is not CapabilityStatus.AVAILABLE
    ]
    if missing:
        pytest.skip(f"upstream capability unavailable: {', '.join(missing)}")
    assert main(["--text", "selftest"]) == 0
    assert "selftest passed" in capsys.readouterr().out


def test_cli_admit_single_scenario(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    _requires(session, "writeback_validator")
    assert main(["admit", "--scenario", "legitimate"]) == EXIT_OK
    assert "legitimate" in capsys.readouterr().out


def test_cli_rejects_unknown_scenario() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["admit", "--scenario", "not-a-scenario"])
    assert exc.value.code == EXIT_BAD_INVOCATION



# --------------------------------------------------------------------------- #
# exit-code contract: execution status is NOT domain verdict
# --------------------------------------------------------------------------- #

COMMANDS = {
    "doctor": ["doctor"],
    "find": ["find", "resource-aware inference placement"],
    "predicates": ["predicates"],
    "outcomes": ["outcomes"],
    "admit": ["admit", "--scenario", "legitimate"],
    "provenance": ["provenance", "--demo"],
    "selftest": ["selftest"],
}

NEEDS_CAPABILITY = [c for c in COMMANDS if c != "doctor"]


def test_every_subcommand_has_a_declared_contract() -> None:
    assert set(COMMANDS) <= set(CONTRACTS)


def test_contracts_name_the_capability_they_require() -> None:
    for command in NEEDS_CAPABILITY:
        assert CONTRACTS[command].required_capability, f"{command} names no capability"


def test_contract_table_renders() -> None:
    text = render_contracts()
    for command in COMMANDS:
        assert command in text
    assert "separate from domain verdict" in text


def test_all_documented_codes_have_meanings() -> None:
    for code in EXIT_MEANINGS:
        assert code in (
            EXIT_OK,
            EXIT_CAPABILITY_UNAVAILABLE,
            EXIT_ASSERTION_FAILED,
            EXIT_BAD_INVOCATION,
        )


def test_declared_capabilities_match_the_provider_set() -> None:
    assert set(declared_capabilities()) <= set(REQUIREMENTS)


# -- the inverse of the original defect --------------------------------------- #


@pytest.mark.parametrize("command", NEEDS_CAPABILITY)
def test_bound_capability_exits_zero_even_when_domain_refuses(
    command: str,
    capsys: pytest.CaptureFixture[str],
    session: VeritasSession,
) -> None:
    """A successful evaluation that REFUSES is still exit 0.

    admit, provenance and predicates all routinely produce governed refusals.
    None of them is a program failure, and none may move the exit code.
    """
    _requires(session, CONTRACTS[command].required_capability)
    code = main(list(COMMANDS[command]))
    out = capsys.readouterr().out
    assert code == EXIT_OK, f"{command} exited {code} on a successful evaluation"
    assert out.strip(), f"{command} produced no output"
    assert not verify_contract(command, code), verify_contract(command, code)


def test_admit_refused_domain_verdict_exits_zero(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """The sharpest case: a legitimate REFUSED must not be an exit failure."""
    _requires(session, "writeback_validator")
    code = main(["admit", "--scenario", "inflate-correlation"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == EdgeVerdict.REFUSED.value
    assert payload["evaluated"] is True
    assert code == EXIT_OK, "a governed refusal was reported as a CLI failure"


def test_provenance_policy_refusal_exits_zero(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """A policy refusal from the registry is data, not a CLI failure."""
    _requires(session, "registry")
    code = main(["provenance", "--demo"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["evaluated"] is True
    assert "permitted" in payload["gate_while_open"]
    assert code == EXIT_OK


def test_find_no_match_is_data_and_exits_zero(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """NO_MATCH must not become global absence, nor a failure.

    The upstream inventory's own wording for NO_MATCH is checked here, because
    that wording is the whole point: the graph being silent is not the world
    being empty.
    """
    _requires(session, "capability_inventory")
    code = main(["find", "qqqq zzzz wwww nonexistent capability"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["evaluated"] is True
    assert code == EXIT_OK, "a not-found verdict was reported as a CLI failure"
    assert payload["verdict"]
    if payload["verdict"] == "NO_MATCH":
        blob = json.dumps(payload).lower()
        assert "not a proven gap" in blob or "graph is silent" in blob or (
            "index searched" in blob or "not a claim" in blob
        ), "NO_MATCH was reported without its scope qualifier"


# -- the original defect: an absent gate must not read as a passing gate ------- #


@pytest.mark.parametrize("command", NEEDS_CAPABILITY)
def test_missing_capability_exits_nonzero(
    command: str,
    capsys: pytest.CaptureFixture[str],
    session: VeritasSession,
) -> None:
    capability = CONTRACTS[command].required_capability
    if session.load.status(capability) is CapabilityStatus.AVAILABLE:
        pytest.skip(f"{capability} resolved in this environment")
    code = main(list(COMMANDS[command]))
    assert code != EXIT_OK, f"{command} exited 0 without {capability}"
    payload = json.loads(capsys.readouterr().out)
    rendered = (
        payload if "evaluated" in payload else payload.get("scenarios", [payload])[0]
    )
    assert rendered.get("evaluated") is False
    assert rendered.get("capability") == CapabilityStatus.UNAVAILABLE.value


def test_doctor_exit_tracks_completeness(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    code = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    if payload["complete"]:
        assert code == EXIT_OK
    else:
        assert code == EXIT_CAPABILITY_UNAVAILABLE


def test_selftest_reports_assertion_failure_separately(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """selftest is the one command whose domain result IS its exit condition."""
    code = main(["selftest"])
    payload = json.loads(capsys.readouterr().out)
    if not payload["evaluated"]:
        assert code == EXIT_CAPABILITY_UNAVAILABLE
    elif payload["passed"]:
        assert code == EXIT_OK
        assert payload["assertions_failed"] == 0
    else:
        assert code == EXIT_ASSERTION_FAILED
        assert payload["assertions_failed"] > 0


def test_exit_code_never_encodes_a_domain_verdict() -> None:
    """Guard: the derivation must not read a domain verdict field.

    No REFUSED / ADMITTED / NO_MATCH / PARTIAL_MATCH value may move the exit
    code in either direction.
    """
    for verdict in (
        EdgeVerdict.REFUSED.value,
        EdgeVerdict.ADMITTED.value,
        EdgeVerdict.ADMITTED_WITH_LOSS.value,
        "NO_MATCH",
        "PARTIAL_MATCH",
        "MULTIPLE_CANDIDATES",
    ):
        payload = {
            "evaluated": True,
            "capability": CapabilityStatus.AVAILABLE.value,
            "verdict": verdict,
        }
        assert from_payload(payload, "writeback_validator") == EXIT_OK, verdict
    assert from_payload(
        {"evaluated": False, "verdict": EdgeVerdict.ADMITTED.value},
        "writeback_validator",
    ) == EXIT_CAPABILITY_UNAVAILABLE
