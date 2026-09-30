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
import sys
from pathlib import Path

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
from veritas_demo.capabilities import (
    CapabilityRecord,
    LocalJsonRegistryProvider,
    RegistryUnavailable,
    load_registries,
)

REQUIRED_FOR_FULL_RUN = (
    "registry",
    "predicate_semantics",
    "writeback_validator",
    "outcome_taxonomy",
)


@pytest.fixture(scope="session")
def session() -> VeritasSession:
    return VeritasSession()


def _write_registry(path, capabilities, **extra):
    """A minimal valid capability registry document."""
    import json

    document = {"registry": path.stem, "version": "1", "capabilities": capabilities}
    document.update(extra)
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _capability(cid="EXAMPLE", **kwargs):
    record = {"id": cid, "name": kwargs.pop("name", cid.lower())}
    record.update(kwargs)
    return record


# --------------------------------------------------------------------------- #
# adapter / loading
# --------------------------------------------------------------------------- #


def test_package_exposes_version() -> None:
    assert VERITAS_VERSION == "0.2.0"


def test_every_declared_capability_is_available(session: VeritasSession) -> None:
    assert set(session.load.statuses) == set(REQUIRED_FOR_FULL_RUN)
    for name in REQUIRED_FOR_FULL_RUN:
        assert session.load.status(name) is CapabilityStatus.AVAILABLE


def test_resolution_names_the_supplying_dependency(session: VeritasSession) -> None:
    report = session.load.as_dict()
    assert set(report["statuses"]) == set(REQUIRED_FOR_FULL_RUN)
    for name, resolution in report["resolutions"].items():
        assert "wyrd-evidence-core" in resolution["detail"], (
            f"{name} does not say which package supplied it"
        )


def test_capabilities_come_from_an_installed_package_not_a_source_tree() -> None:
    """The point of the migration: no private tree may be consulted."""
    import wyrd_evidence_core

    module_dir = Path(wyrd_evidence_core.__file__).parent
    for name in REQUIRED_FOR_FULL_RUN:
        imported = getattr(wyrd_evidence_core, name, None)
        assert imported is not None, f"{name} is not in wyrd-evidence-core"
        if hasattr(imported, "__file__"):
            assert Path(imported.__file__).parent == module_dir


def test_veritas_names_no_private_estate_module() -> None:
    """Static check: no Veritas source file may reference a private module.

    ``wyrd_evidence_core.predicate_semantics`` is the installed dependency; a
    bare ``predicate_semantics`` or ``state_registry`` would be the private tree.
    """
    import re

    import veritas_demo

    package_dir = Path(veritas_demo.__file__).parent
    private = (
        r"state_registry|predicate_semantics|writeback_validator"
        r"|outcome_taxonomy|capability_inventory"
    )
    offenders = []
    for path in package_dir.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if stripped.startswith(("from wyrd_evidence_core", "import wyrd_evidence_core")):
                continue  # this is the installed dependency, not the private tree
            names_private_module = re.search(rf"\b(?:{private})\b", stripped)
            if not names_private_module:
                continue
            is_import = stripped.startswith(("import ", "from "))
            used_as_module = re.search(rf"\b(?:{private})\.", stripped) is not None
            if is_import or (used_as_module and "wyrd_evidence_core." not in stripped):
                offenders.append(f"{path.name}:{lineno}: {stripped}")
    assert offenders == [], offenders


def test_unresolved_registry_is_not_substituted(tmp_path: Path) -> None:
    """A capability registry that cannot be read must raise, not be guessed at.

    The important negative path: a mistyped --registry must not look like a
    genuine capability gap.
    """
    scoped = VeritasSession(
        providers=[LocalJsonRegistryProvider(tmp_path / "absent.json")]
    )
    with pytest.raises(RegistryUnavailable):
        scoped.find_capability("evidence verification audit")


def test_json_render_is_serialisable(session: VeritasSession) -> None:
    payload = json.loads(to_json(session.load.as_dict()))
    assert payload["veritas_version"] == VERITAS_VERSION


# --------------------------------------------------------------------------- #
# capability discovery
# --------------------------------------------------------------------------- #


def test_find_returns_candidate_leads_from_the_bundled_registry(
    session: VeritasSession,
) -> None:
    result = session.find_capability("evidence verification audit")
    assert result["verdict"] in {"PARTIAL_MATCH", "MULTIPLE_CANDIDATES"}
    assert result["candidates"], "the bundled example registry should match"
    lead = result["candidates"][0]
    assert lead["candidate_id"]
    assert lead["source_registry"]
    assert lead["matched_terms"], "a lead must say which terms matched"


def test_find_carries_the_lexical_ranking_caveat(
    session: VeritasSession,
) -> None:
    """A ranking that could be read as a recommendation is a defect."""
    result = session.find_capability("evidence verification audit")
    assert "recommendation" in result["note"].lower()
    assert "NOT" in result["note"]


def test_no_match_means_absent_from_these_registries_only(
    session: VeritasSession,
) -> None:
    result = session.find_capability("brew coffee on a lark")
    assert result["verdict"] == "NO_MATCH"
    assert result["candidates"] == []
    assert result["registries_searched"], "it must say what it searched"


def test_find_searches_a_caller_supplied_registry(tmp_path: Path) -> None:
    """The design goal: any caller registry, with no private estate involved."""
    path = _write_registry(
        tmp_path / "mine.json",
        [
            _capability(
                "MY_TELEMETRY_PIPELINE",
                name="telemetry pipeline",
                terms=["telemetry", "pipeline", "metrics"],
                status="implemented",
                callable=True,
            )
        ],
    )
    scoped = VeritasSession(providers=[LocalJsonRegistryProvider(path)])
    hit = scoped.find_capability("telemetry pipeline metrics")
    assert hit["candidates"], "a caller registry must be searchable"
    assert hit["candidates"][0]["candidate_id"] == "MY_TELEMETRY_PIPELINE"

    miss = scoped.find_capability("evidence verification audit")
    assert miss["verdict"] == "NO_MATCH", "the example registry must not leak in"


def test_an_explicit_registry_is_not_mixed_with_the_bundled_example(
    tmp_path: Path,
) -> None:
    path = _write_registry(tmp_path / "mine.json", [_capability("ONLY_THIS")])
    providers = load_registries(path)
    assert len(providers) == 1
    assert providers[0].name == "mine.json"


def test_an_unreadable_registry_does_not_fall_back_to_the_example(
    tmp_path: Path,
) -> None:
    scoped = VeritasSession(
        providers=[LocalJsonRegistryProvider(tmp_path / "absent.json")]
    )
    with pytest.raises(RegistryUnavailable):
        scoped.find_capability("anything at all")


def test_a_malformed_registry_is_reported_as_unavailable(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RegistryUnavailable):
        LocalJsonRegistryProvider(bad).load()

    no_key = tmp_path / "nokey.json"
    no_key.write_text('{"registry": "x"}', encoding="utf-8")
    with pytest.raises(RegistryUnavailable):
        LocalJsonRegistryProvider(no_key).load()


def test_environment_variable_selects_a_registry(tmp_path: Path) -> None:
    path = _write_registry(tmp_path / "from_env.json", [_capability("FROM_ENV")])
    providers = load_registries(env={"VERITAS_CAPABILITY_REGISTRY": str(path)})
    assert providers[0].name == "from_env.json"
    assert providers[0].load()[0].id == "FROM_ENV"


def test_unknown_record_fields_are_preserved_not_rejected(tmp_path: Path) -> None:
    path = _write_registry(
        tmp_path / "ext.json",
        [_capability("EXT", terms=["widget"], extra_ontology={"kind": "thing"})],
    )
    record = LocalJsonRegistryProvider(path).load()[0]
    assert record.extra == {"extra_ontology": {"kind": "thing"}}


def test_a_registered_but_uncallable_capability_is_reported_as_such(
    tmp_path: Path,
) -> None:
    path = _write_registry(
        tmp_path / "planned.json",
        [_capability(
            "PLANNED", terms=["planned", "widget"], status="planned", callable=False
        )],
    )
    scoped = VeritasSession(providers=[LocalJsonRegistryProvider(path)])
    lead = scoped.find_capability("planned widget")["candidates"][0]
    assert lead["callable"] is False
    assert lead["status"] == "planned"


def test_a_single_term_hit_is_treated_as_noise(tmp_path: Path) -> None:
    """One incidental word is not a lead. Refusal must stay reachable."""
    path = _write_registry(
        tmp_path / "sparse.json",
        [_capability("SPARSE", name="sparse registry", description="a registry")],
    )
    scoped = VeritasSession(providers=[LocalJsonRegistryProvider(path)])
    assert scoped.find_capability("registry")["verdict"] == "NO_MATCH"


def test_the_bundled_example_registry_is_clearly_synthetic() -> None:
    """It must never be mistakable for a real inventory."""
    from veritas_demo.capabilities import BUNDLED_EXAMPLE

    document = json.loads(BUNDLED_EXAMPLE.read_text(encoding="utf-8"))
    assert document["synthetic"] is True
    assert "SYNTHETIC" in document["_note"].upper()
    for record in document["capabilities"]:
        assert record["id"].startswith("EXAMPLE_"), record["id"]


def test_no_private_concept_graph_is_present_anywhere() -> None:
    """The 61-concept G1 graph must not appear in the repo or the wheel."""
    import veritas_demo

    package_dir = Path(veritas_demo.__file__).parent
    files = sorted(p.name for p in package_dir.rglob("*") if p.is_file())
    assert "capability_inventory.py" not in files
    assert not [f for f in files if f.endswith(".jsonl")], files
    assert not [f for f in files if "concept" in f.lower()], files


# --------------------------------------------------------------------------- #
# predicate lattice
# --------------------------------------------------------------------------- #


def test_predicate_lattice_exposes_strength_and_powers(session: VeritasSession) -> None:
    lattice = session.predicate_lattice()
    assert lattice["predicate_count"] >= 20
    assert lattice["self_check_failures"] == 0
    names = {row["predicate"] for row in lattice["predicates"]}
    assert {"CAUSES", "ASSOCIATED_WITH", "OWNED_BY_OPERATOR"} <= names


def test_authority_predicates_are_the_only_ownership_granting_ones(
    session: VeritasSession,
) -> None:
    lattice = session.predicate_lattice()
    granting = [
        row["predicate"] for row in lattice["predicates"] if row["may_establish_ownership"]
    ]
    assert set(granting) == {"OWNED_BY_CONCEPT", "OWNED_BY_OPERATOR"}


def test_causal_predicates_are_the_only_causation_implying_ones(
    session: VeritasSession,
) -> None:
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
    spec = SCENARIOS[scenario]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert result["verdict"] == expected


def test_correlation_to_causation_is_refused_with_its_named_reason(
    session: VeritasSession,
) -> None:
    spec = SCENARIOS["inflate-correlation"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    codes = {f["code"] for f in result["refused"]}
    assert "CAUSATION_FROM_CORRELATION" in codes


def test_path_to_concept_identity_is_refused(session: VeritasSession) -> None:
    spec = SCENARIOS["escalate-identity"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert "IDENTITY_ESCALATION" in {f["code"] for f in result["refused"]}


def test_path_ownership_is_refused(session: VeritasSession) -> None:
    spec = SCENARIOS["escalate-ownership"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert "OWNERSHIP_ESCALATION" in {f["code"] for f in result["refused"]}


def test_unregistered_predicate_is_refused(session: VeritasSession) -> None:
    spec = SCENARIOS["invent-predicate"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert "UNREGISTERED_PREDICATE" in {f["code"] for f in result["refused"]}


def test_weakening_is_recorded_as_a_loss_not_a_refusal(session: VeritasSession) -> None:
    spec = SCENARIOS["weakening-loss"]
    result = session.admit_edges(spec["before"], spec["proposed"])
    assert result["refused"] == []
    assert result["admissible_losses"], "a downgrade must be recorded, not silently accepted"


def test_admission_is_deterministic(session: VeritasSession) -> None:
    spec = SCENARIOS["inflate-correlation"]
    first = session.admit_edges(spec["before"], spec["proposed"])
    second = session.admit_edges(spec["before"], spec["proposed"])
    assert to_json(first) == to_json(second)


def test_a_missing_dependency_fails_loudly_at_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing evidence core must stop the program, not degrade it.

    There is no local approximation to fall back on, by design: a Veritas that
    quietly admitted claims when its evidence lattice was missing would be worse
    than one that will not start.
    """
    import builtins
    import importlib

    import veritas_demo.core  # noqa: F401  (ensure loaded before the patch)

    real_import = builtins.__import__

    def refuse(name, *args, **kwargs):
        if name.startswith("wyrd_evidence_core"):
            raise ModuleNotFoundError("No module named 'wyrd_evidence_core'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", refuse)
    monkeypatch.delitem(sys.modules, "veritas_demo.core", raising=False)
    try:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("veritas_demo.core")
    finally:
        monkeypatch.undo()
        importlib.import_module("veritas_demo.core")


def test_no_local_substitution_of_a_governed_rule() -> None:
    """Veritas must not carry a fallback implementation of any evidence rule."""
    import inspect

    import veritas_demo.core as core_module

    source = inspect.getsource(core_module)
    for forbidden in (
        "except ImportError",
        "hasattr(module",
        "if module is None",
    ):
        assert forbidden not in source, (
            f"core.py contains {forbidden!r}: a missing capability must be "
            "loud, never quietly tolerated"
        )


# --------------------------------------------------------------------------- #
# outcome taxonomy
# --------------------------------------------------------------------------- #


def test_outcome_vocabulary_partitions_into_families(session: VeritasSession) -> None:
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
    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    verification = session.verify_provenance(registry, "ROUTER")
    assert verification["chain_valid"] is True
    assert verification["records_checked"] >= 1


def test_open_component_permits_operation(session: VeritasSession) -> None:
    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    gate = session.policy_gate(registry, "ROUTER", "implementation")
    assert gate["permitted"] is True


def test_terminal_disposition_blocks_operation(session: VeritasSession) -> None:
    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    from wyrd_evidence_core import registry_schema as schema
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
    import json as _json
    from pathlib import Path

    registry = session.open_registry()
    session.register_component(registry, name="ROUTER", repository="r", path="p.py")
    from wyrd_evidence_core import registry_schema as schema
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

    from wyrd_evidence_core.registry_schema import RegistryCorruptionError

    with pytest.raises(RegistryCorruptionError):
        session.open_registry(path.parent)


def test_unknown_component_is_permitted_not_forbidden(session: VeritasSession) -> None:
    registry = session.open_registry()
    gate = session.policy_gate(registry, "NEVER_REGISTERED", "implementation")
    assert gate["permitted"] is True
    assert "unknown != forbidden" in gate["reason"]


def test_open_registry_defaults_to_a_throwaway_directory(session: VeritasSession) -> None:
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


def test_declared_capabilities_are_all_supplied_by_a_real_implementation() -> None:
    """Four come from the evidence core; capability_registry is Veritas' own."""
    import veritas_demo.capabilities as capabilities_module
    from veritas_demo.core import EVIDENCE_CORE_CAPABILITIES

    declared = set(declared_capabilities())
    assert declared - {"capability_registry"} <= set(EVIDENCE_CORE_CAPABILITIES)
    assert hasattr(capabilities_module, "search"), (
        "the one capability Veritas owns must actually exist"
    )


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
    code = main(list(COMMANDS[command]))
    out = capsys.readouterr().out
    assert code == EXIT_OK, f"{command} exited {code} on a successful evaluation"
    assert out.strip(), f"{command} produced no output"
    assert not verify_contract(command, code), verify_contract(command, code)


def test_admit_refused_domain_verdict_exits_zero(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """The sharpest case: a legitimate REFUSED must not be an exit failure."""
    code = main(["admit", "--scenario", "inflate-correlation"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"] == EdgeVerdict.REFUSED.value
    assert payload["evaluated"] is True
    assert code == EXIT_OK, "a governed refusal was reported as a CLI failure"


def test_provenance_policy_refusal_exits_zero(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """A policy refusal from the registry is data, not a CLI failure."""
    code = main(["provenance", "--demo"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["evaluated"] is True
    assert "permitted" in payload["gate_while_open"]
    assert code == EXIT_OK


def test_find_no_match_is_data_and_exits_zero(
    capsys: pytest.CaptureFixture[str], session: VeritasSession
) -> None:
    """NO_MATCH must not become global absence, nor a failure.

    The wording matters as much as the code: "the registries searched are silent"
    is not "the capability does not exist".
    """
    code = main(["find", "qqqq zzzz wwww nonexistent capability"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["evaluated"] is True
    assert code == EXIT_OK, "a not-found verdict was reported as a CLI failure"
    assert payload["verdict"]
    if payload["verdict"] == "NO_MATCH":
        blob = json.dumps(payload).lower()
        assert "not proof" in blob or "not that" in blob, (
            "NO_MATCH was reported without its scope qualifier"
        )
        assert payload["registries_searched"], "it must say what it searched"


def test_find_with_an_unreadable_registry_exits_nonzero(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """A failure to answer is not an answer."""
    code = main([
        "find", "evidence verification audit",
        "--registry", str(tmp_path / "absent.json"),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == EXIT_CAPABILITY_UNAVAILABLE
    assert payload["verdict"] == "REGISTRY_UNAVAILABLE"
    assert payload["evaluated"] is False
    assert payload["candidates"] == []


def test_find_exits_zero_against_a_user_registry(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = _write_registry(
        tmp_path / "mine.json",
        [_capability(
            "MY_TELEMETRY_PIPELINE", name="telemetry pipeline",
            terms=["telemetry", "pipeline", "metrics"], status="implemented",
        )],
    )
    code = main([
        "find", "telemetry pipeline metrics", "--registry", str(path),
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK
    assert payload["candidates"][0]["candidate_id"] == "MY_TELEMETRY_PIPELINE"


def test_doctor_reports_the_configured_registries(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    path = _write_registry(tmp_path / "mine.json", [_capability("X")])
    code = main(["doctor"])
    payload = json.loads(capsys.readouterr().out)
    assert code == EXIT_OK
    assert payload["registries"], "doctor must report which registries find uses"
    assert payload["registries"][0]["readable"] is True


# -- the original defect: an absent gate must not read as a passing gate ------- #


@pytest.mark.parametrize(
    "command", [c for c in NEEDS_CAPABILITY if c != "find"]
)
def test_missing_capability_exits_nonzero(
    command: str,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    session: VeritasSession,
) -> None:
    """An absent gate must not read as a passing gate.

    The absence is simulated rather than waited for, because with the evidence
    core installed as an ordinary dependency a missing capability means a broken
    install -- and the CLI must still refuse rather than answer.
    """
    capability = CONTRACTS[command].required_capability
    assert capability in session.load.statuses, (
        f"{command} declares {capability}, which is not a known capability"
    )

    from veritas_demo.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(COMMANDS[command])
    degraded = VeritasSession()
    degraded.load.statuses[capability] = CapabilityStatus.UNAVAILABLE

    monkeypatch.setattr("veritas_demo.cli.VeritasSession", lambda *a, **k: degraded)
    code = args.func(degraded, args)
    assert code != EXIT_OK, f"{command} exited 0 without {capability}"
    payload = json.loads(capsys.readouterr().out)
    rendered = (
        payload if "evaluated" in payload else payload.get("scenarios", [payload])[0]
    )
    assert rendered.get("evaluated") is False
    assert rendered.get("capability") == CapabilityStatus.UNAVAILABLE.value


def test_every_declared_capability_is_a_real_capability() -> None:
    """No command may declare a requirement that nothing implements."""
    from veritas_demo.capabilities import search as capability_search
    from veritas_demo.core import EVIDENCE_CORE_CAPABILITIES

    known = set(EVIDENCE_CORE_CAPABILITIES) | {
        name for name in ("capability_registry",) if callable(capability_search)
    }
    for command, contract in CONTRACTS.items():
        required = contract.required_capability
        if required:
            assert required in known, f"{command} declares unknown {required}"


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
