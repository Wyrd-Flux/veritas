"""Command-line entry point for Veritas.

    veritas-demo doctor
    veritas-demo find "evidence verification" --registry ./my-registry.json
    veritas-demo predicates
    veritas-demo outcomes
    veritas-demo admit --scenario SCENARIO
    veritas-demo provenance --demo
    veritas-demo selftest

All output is JSON unless ``--text`` is passed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from . import VERITAS_VERSION
from .core import CapabilityStatus, EdgeVerdict, VeritasSession, to_json
from .exit_codes import (
    EXIT_ASSERTION_FAILED,
    EXIT_BAD_INVOCATION,
    EXIT_CAPABILITY_UNAVAILABLE,
    EXIT_OK,
    from_payload,
    render_contracts,
    unavailable,
)
from .capabilities import (
    ENV_REGISTRY,
    LocalJsonRegistryProvider,
    RegistryUnavailable,
)

SCENARIOS: dict[str, dict[str, Any]] = {
    "inflate-correlation": {
        "description": "Promote an observed association to a causal claim.",
        "before": [
            {
                "subject": "ROUTER",
                "predicate": "ASSOCIATED_WITH",
                "obj": "latency_p99",
                "evidence": ["obs:bench-2026-09-30"],
            }
        ],
        "proposed": [
            {
                "subject": "ROUTER",
                "predicate": "CAUSES",
                "obj": "latency_p99",
                "evidence": ["obs:bench-2026-09-30"],
            }
        ],
    },
    "escalate-identity": {
        "description": "Assert that a file path establishes a concept identity.",
        "before": [
            {
                "subject": "congestion_control",
                "predicate": "LOCATED_IN",
                "obj": "src/router.py",
                "evidence": ["read:src/router.py"],
            }
        ],
        "proposed": [
            {
                "subject": "src/router.py",
                "predicate": "DEFINES_CONCEPT",
                "obj": "congestion_control",
                "evidence": ["read:src/router.py"],
            }
        ],
    },
    "escalate-ownership": {
        "description": "Claim operator ownership from a structural location fact.",
        "before": [
            {
                "subject": "src/router.py",
                "predicate": "LOCATED_IN",
                "obj": "repo",
                "evidence": ["read:src/router.py"],
            }
        ],
        "proposed": [
            {
                "subject": "src/router.py",
                "predicate": "OWNED_BY_OPERATOR",
                "obj": "repo",
                "evidence": ["read:src/router.py"],
            }
        ],
    },
    "invent-predicate": {
        "description": "Introduce a relation that is not in the lattice.",
        "before": [
            {
                "subject": "ROUTER",
                "predicate": "IMPLEMENTS_CONCEPT",
                "obj": "congestion_control",
                "evidence": ["read:src/router.py"],
            }
        ],
        "proposed": [
            {
                "subject": "ROUTER",
                "predicate": "VIBES_WITH",
                "obj": "congestion_control",
                "evidence": ["read:src/router.py"],
            }
        ],
    },
    "weakening-loss": {
        "description": "Downgrade a causal claim to an association: an honest loss.",
        "before": [
            {
                "subject": "ROUTER",
                "predicate": "CAUSES",
                "obj": "latency_p99",
                "evidence": ["obs:bench-2026-09-30"],
            }
        ],
        "proposed": [
            {
                "subject": "ROUTER",
                "predicate": "ASSOCIATED_WITH",
                "obj": "latency_p99",
                "evidence": ["obs:bench-2026-09-30"],
            }
        ],
    },
    "legitimate": {
        "description": "A claim that holds up under every gate.",
        "before": [
            {
                "subject": "ROUTER",
                "predicate": "IMPLEMENTS_CONCEPT",
                "obj": "congestion_control",
                "evidence": ["read:src/router.py"],
            }
        ],
        "proposed": [
            {
                "subject": "src/router.py",
                "predicate": "LOCATED_IN",
                "obj": "repo",
                "evidence": ["read:src/router.py"],
            }
        ],
    },
}


def _emit(payload: Any, as_text: bool, text: str | None = None) -> None:
    if as_text and text is not None:
        print(text)
    else:
        print(to_json(payload))


def _available(session: VeritasSession, capability: str) -> bool:
    return session.load.status(capability) is CapabilityStatus.AVAILABLE



def _cmd_doctor(session: VeritasSession, args: argparse.Namespace) -> int:
    """Report the evidence capabilities and which registries ``find`` will search."""
    report = session.load
    payload = report.as_dict()

    providers = session.providers
    try:
        if not providers:
            from .capabilities import load_registries

            providers = load_registries()
        registry_rows = []
        for provider in providers:
            row = {"name": provider.name, "readable": True, "capabilities": None}
            try:
                row["capabilities"] = len(provider.load())
            except RegistryUnavailable as exc:
                row["readable"] = False
                row["detail"] = str(exc)
            registry_rows.append(row)
    except RegistryUnavailable as exc:  # pragma: no cover - defensive
        registry_rows = [{"name": "(unresolved)", "readable": False, "detail": str(exc)}]

    payload["registries"] = registry_rows
    payload["evaluated"] = True
    all_readable = all(r.get("readable") for r in registry_rows)
    payload["exit_code"] = (
        EXIT_OK if (report.complete and all_readable) else EXIT_CAPABILITY_UNAVAILABLE
    )

    lines = [report.render(), "", "capability registries for 'find'"]
    for row in registry_rows:
        mark = "ok  " if row.get("readable") else "MISS"
        detail = (
            f"{row.get('capabilities')} capabilities"
            if row.get("readable")
            else row.get("detail", "unreadable")
        )
        lines.append(f"  [{mark}] {row.get('name'):34s} {detail}")
    lines.append("")
    lines.append(
        "point 'find' at your own registry with --registry PATH, or set "
        "VERITAS_CAPABILITY_REGISTRY"
    )
    _emit(payload, args.text, "\n".join(lines))
    return int(payload["exit_code"])


def _cmd_find(session: VeritasSession, args: argparse.Namespace) -> int:
    """Search the configured capability registries for candidate leads.

    Exit codes are separated from the verdict: a query that runs and returns
    NO_MATCH is a completed query, so it exits 0. A registry that cannot be read
    is a failure to answer, and exits non-zero.
    """
    try:
        result = session.find_capability(args.query)
    except RegistryUnavailable as exc:
        payload = {
            "query": args.query,
            "verdict": "REGISTRY_UNAVAILABLE",
            "evaluated": False,
            "candidates": [],
            "detail": str(exc),
            "note": (
                "the configured registry could not be read, so no search was "
                "performed. This is deliberately not reported as NO_MATCH: an "
                "unreadable registry is a failure to answer, and treating it as "
                "an answer would make a mistyped path look like a capability gap."
            ),
            "exit_code": EXIT_CAPABILITY_UNAVAILABLE,
        }
        _emit(
            payload,
            args.text,
            "\n".join([
                f"query: {args.query}",
                "verdict: REGISTRY_UNAVAILABLE",
                f"detail: {exc}",
                "",
                "no fallback registry was searched. Point --registry at a readable",
                "capability registry, or unset it to use the bundled example.",
            ]),
        )
        return EXIT_CAPABILITY_UNAVAILABLE

    result["evaluated"] = True
    lines = [
        f"query     : {result.get('query')}",
        f"verdict   : {result.get('verdict')}",
        f"registries: {', '.join(result.get('registries_searched') or []) or '(none)'}",
        f"qualifier : {result.get('qualifier', '')}",
        "",
        "candidates (lexical leads, not recommendations):",
    ]
    if not result.get("candidates"):
        lines.append("  (none)")
    for cand in result.get("candidates", []) or []:
        lines.append(
            f"  {cand.get('candidate_id')}"
            f"  [{cand.get('status')}]"
            f"  score={cand.get('lexical_score')}"
            f"  terms={','.join(cand.get('matched_terms') or [])}"
        )
        if cand.get("callable") is False:
            lines.append("      callable: NO -- registered but not implemented")
        if cand.get("source"):
            lines.append(f"      source: {cand['source']}")
        if cand.get("evidence_notes"):
            lines.append(f"      evidence: {cand['evidence_notes']}")
        if cand.get("verification"):
            lines.append(f"      verified by: {', '.join(cand['verification'])}")
    lines.extend(["", f"note: {result.get('note', '')}"])
    _emit(result, args.text, "\n".join(lines))
    return EXIT_OK


def _cmd_predicates(session: VeritasSession, args: argparse.Namespace) -> int:
    lattice = session.predicate_lattice()
    lines = [
        f"predicates: {lattice.get('predicate_count')}"
        f"   self_check failures: {lattice.get('self_check_failures')}",
        "",
        f"{'PREDICATE':34s} {'STRENGTH':12s} DIR  CAUSE ID  OWN",
    ]
    for row in lattice.get("predicates", []) or []:
        lines.append(
            f"{row['predicate']:34s} {row['strength_name']:12s}"
            f" {'y' if row['directional'] else 'n':^3s}"
            f" {'y' if row['implies_causation'] else 'n':^6s}"
            f" {'y' if row['may_establish_identity'] else 'n':^4s}"
            f" {'y' if row['may_establish_ownership'] else 'n':^4s}"
        )
    lattice["evaluated"] = _available(session, "predicate_semantics")
    _emit(lattice, args.text, "\n".join(lines))
    return from_payload(lattice, "predicate_semantics")


def _cmd_outcomes(session: VeritasSession, args: argparse.Namespace) -> int:
    data = session.outcome_classes()
    lines = ["outcome classes:"]
    for group in ("resolved", "refused", "open"):
        lines.append(f"  {group}: {', '.join(data.get(group, []) or [])}")
    data["evaluated"] = _available(session, "outcome_taxonomy")
    _emit(data, args.text, "\n".join(lines))
    return from_payload(data, "outcome_taxonomy")


def _cmd_admit(session: VeritasSession, args: argparse.Namespace) -> int:
    names = [args.scenario] if args.scenario else list(SCENARIOS)
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(sorted(SCENARIOS))}", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    results = []
    for name in names:
        spec = SCENARIOS[name]
        outcome = session.admit_edges(
            spec["before"], spec["proposed"], authorization=tuple(args.authorize or ())
        )
        results.append({"scenario": name, "description": spec["description"], **outcome})

    evaluated = _available(session, "writeback_validator")
    for row in results:
        row["evaluated"] = evaluated
    if len(results) == 1:
        payload: Any = dict(results[0])
    else:
        payload = {"scenarios": results, "evaluated": evaluated}

    lines = []
    for row in results:
        lines.append(f"[{row['verdict']:>20s}] {row['scenario']}  {row['description']}")
        for finding in row.get("refused", []):
            lines.append(f"     refused: {finding['code']} on {finding['edge']}")
        for finding in row.get("admissible_losses", []):
            lines.append(f"     loss:    {finding['code']} on {finding['edge']}")
    _emit(payload, args.text, "\n".join(lines))
    # A governed REFUSED is a successful evaluation. Only an absent gate fails.
    if len(results) == 1:
        return from_payload(payload, "writeback_validator")
    code = EXIT_OK
    for row in results:
        code = max(code, from_payload(row, "writeback_validator"))
    return code


def _cmd_provenance(session: VeritasSession, args: argparse.Namespace) -> int:
    """Register a component, gate an operation, and verify the history chain."""
    registry = session.open_registry(None if args.demo else args.data_dir)
    session.register_component(
        registry,
        name=args.component,
        repository=args.repository,
        path=args.path,
        established_date=args.date,
    )
    gate_open = session.policy_gate(registry, args.component, "implementation")
    verification = session.verify_provenance(registry, args.component)
    unknown = session.policy_gate(registry, "NEVER_REGISTERED", "implementation")
    payload = {
        "registered": args.component,
        "capability": session.load.status("registry").value,
        "evaluated": _available(session, "registry"),
        "gate_while_open": gate_open,
        "chain": verification,
        "unknown_component": unknown,
        "note": (
            "unknown components are permitted: absence from the registry is "
            "not evidence of prohibition"
        ),
    }
    lines = [
        f"registered {args.component}",
        f"  gate(OPEN, implementation): {gate_open['permitted']} - {gate_open['reason']}",
        f"  chain valid: {verification['chain_valid']}"
        f"  records: {verification['records_checked']}",
        f"  gate(NEVER_REGISTERED, implementation): {unknown['permitted']}"
        f" - {unknown['reason']}",
    ]
    _emit(payload, args.text, "\n".join(lines))
    return from_payload(payload, "registry")


def _cmd_selftest(session: VeritasSession, args: argparse.Namespace) -> int:
    expected = {
        "inflate-correlation": "REFUSED",
        "escalate-identity": "REFUSED",
        "escalate-ownership": "REFUSED",
        "invent-predicate": "REFUSED",
        "weakening-loss": "ADMITTED_WITH_LOSS",
        "legitimate": "ADMITTED",
    }
    rows = []
    failures = 0
    evaluated = _available(session, "writeback_validator")
    for name, want in expected.items():
        spec = SCENARIOS[name]
        got = session.admit_edges(spec["before"], spec["proposed"])
        ok = got.get("verdict") == want
        if not evaluated:
            ok = False
        failures += 0 if ok else 1
        rows.append(
            {
                "scenario": name,
                "expected": want,
                "actual": got.get("verdict"),
                "pass": ok,
                "codes": [f["code"] for f in got.get("refused", [])]
                + [f["code"] for f in got.get("admissible_losses", [])],
            }
        )
    if not evaluated:
        code = EXIT_CAPABILITY_UNAVAILABLE
    elif failures:
        code = EXIT_ASSERTION_FAILED
    else:
        code = EXIT_OK
    payload = {
        "veritas_version": VERITAS_VERSION,
        "capability": (
            CapabilityStatus.AVAILABLE.value
            if evaluated
            else CapabilityStatus.UNAVAILABLE.value
        ),
        "evaluated": evaluated,
        "passed": evaluated and not failures,
        "assertions_failed": failures,
        "results": rows,
        "exit_code": code,
    }
    lines = []
    for row in rows:
        mark = "PASS" if row["pass"] else "FAIL"
        lines.append(f"  [{mark}] {row['scenario']:22s} {row['actual']}  {row['codes']}")
    if evaluated:
        lines.append(f"  selftest {'passed' if not failures else 'FAILED'}")
    else:
        lines.append("  selftest NOT RUN -- writeback_validator unavailable")
    _emit(payload, args.text, "\n".join(lines))
    return code


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that exits with the documented bad-invocation code.

    argparse hardcodes exit 2 for a malformed invocation, which collides with
    the documented capability-unavailable code. Subclassing keeps the
    contract table honest.
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_BAD_INVOCATION)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="veritas-demo",
        description=(
            "Veritas: governed claim admission and capability discovery. Evidence "
            "semantics, writeback validation, the outcome taxonomy and the "
            "component registry come from wyrd-evidence-core. Capability discovery "
            "searches registries you supply."
        ),
    )
    parser.add_argument("--version", action="version", version=VERITAS_VERSION)
    parser.add_argument(
        "--text", action="store_true", help="render human-readable output instead of JSON"
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    sub.add_parser(
        "doctor",
        help="report the evidence capabilities and the configured registries",
    ).set_defaults(func=_cmd_doctor)

    find = sub.add_parser(
        "find",
        help="search capability registries for candidate leads",
        description=(
            "Search capability registries for candidate leads. A lead is a "
            "lexical near-match, not a capability identity and not a "
            "recommendation. NO_MATCH means no query term appeared in the "
            "registries searched, not that the capability does not exist."
        ),
    )
    find.add_argument("query")
    find.add_argument(
        "--registry",
        default=None,
        metavar="PATH",
        help=(
            "capability registry JSON to search (default: "
            f"{ENV_REGISTRY}, else the bundled synthetic example)"
        ),
    )
    find.set_defaults(func=_cmd_find)

    sub.add_parser("predicates", help="show the registered predicate lattice").set_defaults(
        func=_cmd_predicates
    )

    sub.add_parser("outcomes", help="show the outcome classification vocabulary").set_defaults(
        func=_cmd_outcomes
    )

    admit = sub.add_parser("admit", help="run edge admission scenarios")
    admit.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        help="run one scenario; omit to run all",
    )
    admit.add_argument(
        "--authorize",
        action="append",
        help="authorizing evidence ref (repeatable)",
    )
    admit.set_defaults(func=_cmd_admit)

    prov = sub.add_parser("provenance", help="demonstrate the policy gate and hash chain")
    prov.add_argument("--component", default="ROUTER")
    prov.add_argument("--date", default="2026-09-30")
    prov.add_argument("--repository", default="your-project",
                      help="repository name recorded with the component")
    prov.add_argument("--path", default="src/your_project/router.py",
                      help="path recorded with the component")
    prov.add_argument("--data-dir", default=None)
    prov.add_argument(
        "--demo",
        action="store_true",
        help="use a throwaway temporary registry (default when no --data-dir)",
    )
    prov.set_defaults(func=_cmd_provenance)

    sub.add_parser("selftest", help="verify each scenario refuses for the right reason").set_defaults(
        func=_cmd_selftest
    )
    sub.add_parser(
        "exit-codes", help="print the documented exit-code contract per subcommand"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "exit-codes":
        print(render_contracts())
        return EXIT_OK
    session = VeritasSession(
        providers=(
            [LocalJsonRegistryProvider(Path(args.registry))]
            if getattr(args, "registry", None)
            else None
        )
    )
    return int(args.func(session, args))


if __name__ == "__main__":
    raise SystemExit(main())
