# Demo notes

How each claim in this README was verified, and what to watch for when running
it. Recorded 2026-09-30 on Windows / CPython 3.11.9.

## Verified commands

All run from an isolated virtualenv with Veritas installed as a wheel, and all
upstream bindings supplied by environment variable only.

| Command | Result |
|---|---|
| `pip install .` into a fresh venv | succeeds; `veritas-demo` console script on PATH |
| `import veritas_demo` with nothing installed | succeeds; **zero** upstream modules in `sys.modules` |
| `veritas-demo --version` | `0.1.0` |
| `veritas-demo exit-codes` | prints the contract table from the code implementing it |
| `veritas-demo doctor` | 5/5 `AVAILABLE`, exit 0 |
| `veritas-demo find "evidence verification"` | `PARTIAL_MATCH`, 1 candidate with qualifier |
| `veritas-demo predicates` | 24 predicates, 0 self-check failures |
| `veritas-demo outcomes` | 3 families, disjoint |
| `veritas-demo admit` | 6 scenarios, 4 refused / 1 loss / 1 admitted |
| `veritas-demo provenance --demo` | chain valid, 1 record; unknown component permitted |
| `veritas-demo selftest` | 6/6 pass, exit 0 |
| `pytest -q` | 55 passed, 6 skipped |

### Exit-code matrix, observed

Checked for every subcommand in both environments. This is the distinction that
mattered most during development, so it is recorded per command rather than
summarised.

| Command | bound | unbound |
|---|---:|---:|
| `doctor` | 0 | 2 |
| `find anything` | 0 | 2 |
| `predicates` | 0 | 2 |
| `outcomes` | 0 | 2 |
| `admit` | 0 | 2 |
| `admit --scenario legitimate` | 0 | 2 |
| `admit --scenario inflate-correlation` (**a legitimate REFUSED**) | **0** | 2 |
| `provenance --demo` | 0 | 2 |
| `selftest` | 0 | 2 |
| `exit-codes` | 0 | 0 |
| malformed invocation | 64 | 64 |

The row that justifies the contract: `inflate-correlation` returns
`REFUSED` — the correct, expected, *successful* answer — and exits **0**.
`legitimate` with no validator returns `UNAVAILABLE` and exits **2**. Neither
verdict leaks into the other.

Two defects were found and fixed while establishing this:

1. **An absent gate exited 0.** `admit` printed `"verdict": "UNAVAILABLE"` and
   returned success. Fixed; pinned by `test_missing_capability_exits_nonzero`.
2. **A blanket rule conflated the dimensions.** The first fix applied one
   `_exit_for` to every payload, which would also have made a governed
   `REFUSED` exit non-zero. Replaced with a per-command contract in
   `veritas_demo/exit_codes.py`; pinned by
   `test_bound_capability_exits_zero_even_when_domain_refuses` and the guard
   test `test_exit_code_never_encodes_a_domain_verdict`.

`argparse` also needed subclassing: it hardcodes exit 2 for a malformed
invocation, which collided with the documented capability-unavailable code.

## The interesting results

### Refusals are specific, not generic

Each scenario is refused with a different set of codes, and the codes are the
upstream module's own vocabulary:

```
inflate-correlation  RELATION_TYPE_SUBSTITUTION, RELATION_STRENGTHENING,
                     CAUSATION_FROM_CORRELATION
escalate-identity    IDENTITY_ESCALATION
escalate-ownership   RELATION_TYPE_SUBSTITUTION, RELATION_STRENGTHENING,
                     OWNERSHIP_ESCALATION
invent-predicate     UNREGISTERED_PREDICATE
```

The escalation cases report both the specific violation *and* the generic
strength change, which is what makes them legible to someone who has not read
the validator's source.

### Admitting a weaker claim is allowed, and recorded

```
weakening-loss  ADMITTED_WITH_LOSS  ADMISSIBLE_WEAKENING
```

`CAUSES` → `ASSOCIATED_WITH` passes. That asymmetry is the point: the gate
blocks inflation and permits deflation, because refusing honest weakening would
teach people to stop reporting.

### The disposition gate does not consult per-operation policy while `OPEN`

`can_modify` returns "all operations permitted" for an `OPEN` component before
it reaches the per-operation policy lookup, so a `PROHIBITED` reopening policy
has no effect until the component leaves `OPEN`. This matches the upstream
docstring. Recorded in `docs/PROVENANCE.md` because it is easy to misread.

### Chain verification has a scope

Editing a `history` record is detected at load:

```
tamper history.action           -> RegistryCorruptionError on load
tamper history.established_by   -> RegistryCorruptionError on load
tamper component.established_by -> loads; chain still reports valid
```

The third is a real limit on what "chain valid" means. Veritas reports
`chain_valid` and `records_checked` separately rather than a single
"unmodified" boolean, precisely so this is visible.

### Unknown is not forbidden

```
gate(NEVER_REGISTERED, implementation): True
  - Component not in registry (unknown != forbidden)
```

An unregistered component permits everything. That is the upstream rule and it
is the opposite of a safe default, so it is worth seeing explicitly: Veritas is
a demo of a rule, not an endorsement of it.

## What a reader should be sceptical of

- **`find` is only as complete as its corpus.** It searches a 61-concept index.
  A `NO_MATCH` means "not in this index", not "does not exist". The `NO_MATCH`
  vs `PARTIAL_MATCH` distinction is preserved rather than flattened.
- **The predicate vocabulary is domain-specific.** `CAUSES` means what that
  estate means by it. Veritas renders the lattice and does not argue the
  vocabulary is universal.
- **`provenance --demo` shows a one-component registry.** It demonstrates the
  gate and the chain, not the scale. The real corpus has 76 components and five
  absolute evidence paths that resolve only on its original machine.
- **The upstream licenses are unresolved.** See `LICENSE`.

## Reproducing the environment

The bindings used for verification, in Git-Bash form:

```console
$ export VERITAS_REGISTRY_PATH=C:/Projects
$ export VERITAS_PREDICATE_SEMANTICS_PATH=C:/G1/tools
$ export VERITAS_WRITEBACK_VALIDATOR_PATH=C:/G1/tools
$ export VERITAS_OUTCOME_TAXONOMY_PATH=C:/G1/tools
$ export VERITAS_CAPABILITY_INVENTORY_PATH=C:/G1/tools
```

Two directories is the whole dependency footprint. `state_registry` is a package
directory; the other four are loose modules in one directory.

Note the asymmetry in the bindings: `VERITAS_REGISTRY_PATH` is `C:/Projects`, the
parent of the `state_registry` package directory, while the other four point at
`C:/G1/tools`, which contains the loose modules directly. Passing the package
directory itself does not resolve `state_registry`.

`writeback_validator` imports `predicate_semantics` as a sibling, so the two
must be resolved from the same place. Veritas handles this: once
`writeback_validator` resolves from a directory, that directory is on
`sys.path` for the import it performs.

`state_registry` needs no installation — pointing `VERITAS_REGISTRY_PATH` at the
directory containing the package directory is sufficient. It has no
`pyproject.toml`.
