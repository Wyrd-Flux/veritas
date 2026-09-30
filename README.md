# Veritas

**Find the capability that already exists. Then make the claim only if it survives.**

Veritas is a small command-line application assembled almost entirely from
capabilities that already exist in a larger evidence-governed estate. It binds
to them through adapters and delegates every decision to them. It contains no
reimplementation of any governed behaviour.

It answers two questions that come up constantly when working inside such an
estate:

1. *Before I build this, does something already do it?*
2. *Can this claim actually be admitted, or is it a dressed-up guess?*

```console
$ veritas-demo find "evidence verification"
query: evidence verification
verdict: PARTIAL_MATCH

candidates:
  JEV_JUST_EVIDENCE_VERIFICATION  [IMPLEMENTED]  score=0.8  qualifier=CALLABLE
      root: <implementation root>
      tests: <test paths>

next: CANDIDATE FOUND. Read the implementation root and check the callable
      surface before building anything new.
```

```console
$ veritas-demo admit
[             REFUSED] inflate-correlation  Promote an observed association to a causal claim.
     refused: RELATION_TYPE_SUBSTITUTION on ROUTER --CAUSES--> latency_p99
     refused: RELATION_STRENGTHENING on ROUTER --CAUSES--> latency_p99
     refused: CAUSATION_FROM_CORRELATION on ROUTER --CAUSES--> latency_p99
[  ADMITTED_WITH_LOSS] weakening-loss  Downgrade a causal claim to an association.
     loss:    ADMISSIBLE_WEAKENING on ROUTER --ASSOCIATED_WITH--> latency_p99
[            ADMITTED] legitimate  A claim that holds up under every gate.
```

---

## Why this demo exists

The estate Veritas draws from is unusual: it refuses to let a statement become
true just because someone wrote it down. Three rules run through all of it.

- **A claim carries evidence.** `writeback_validator` compares a proposed
  relation set against the current one and refuses changes that inflate what
  the evidence supports.
- **A relation has a strength, and the strength only moves with evidence.**
  `predicate_semantics` holds a closed lattice of 24 predicates across six
  strength classes. `CORRELATES_WITH` cannot become `CAUSES` because a document
  used both words.
- **Absence of evidence is not evidence of prohibition, and not of
  permission either.** `state_registry` gates operations by recorded policy,
  and says plainly which authority a blocked operation would need.

Veritas makes those three rules visible in about five minutes of reading. It is
a demo *of the architecture*, not a reimplementation of it: every verdict it
prints came from the upstream module that owns that decision, with its own
refusal code attached.

---

## What it composes

Veritas is a **cross-repository composition**. None of these five capabilities
lives with the others, and they were built independently. Veritas binds to them
at runtime and **reproduces none of their code** — see
[`docs/PROVENANCE.md`](docs/PROVENANCE.md):

| Capability | Upstream module | What it decides |
|---|---|---|
| `registry` | `state_registry` (`C:/Projects/state_registry`) | component state, operation policy, hash-chained provenance |
| `predicate_semantics` | `predicate_semantics` (`C:/G1/tools`) | the predicate strength lattice |
| `writeback_validator` | `writeback_validator` (`C:/G1/tools`) | whether a proposed relation set is admitted |
| `outcome_taxonomy` | `outcome_taxonomy` (`C:/G1/tools`) | how an attempt is classified when it ends |
| `capability_inventory` | `capability_inventory` (`C:/G1/tools`) | which registered systems could do a stated need |

The repository boundaries in the source estate are implementation locations,
not product boundaries. Veritas treats them that way. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the exact dependency map and
[`docs/PROVENANCE.md`](docs/PROVENANCE.md) for what was copied and what was
not.

**Nothing in this repository is a fork of an upstream capability.** The only
files are the adapter layer, the CLI, the scenario definitions, the tests, and
the documentation. See `docs/PROVENANCE.md`.

---

## Install

```console
$ python -m venv .venv
$ .venv/Scripts/python -m pip install -e .          # Windows
$ .venv/bin/python -m pip install -e .               # POSIX
```

Veritas itself has **no runtime dependencies**.

## Bind to the upstream capabilities

The five upstream modules are **not published on PyPI**. Point Veritas at them
with environment variables, each accepting either a `.py` file or a directory
to place on `sys.path`:

| Variable | Points at |
|---|---|
| `VERITAS_REGISTRY_PATH` | directory containing the `state_registry` package |
| `VERITAS_PREDICATE_SEMANTICS_PATH` | directory containing `predicate_semantics.py` |
| `VERITAS_WRITEBACK_VALIDATOR_PATH` | directory containing `writeback_validator.py` |
| `VERITAS_OUTCOME_TAXONOMY_PATH` | directory containing `outcome_taxonomy.py` |
| `VERITAS_CAPABILITY_INVENTORY_PATH` | directory containing `capability_inventory.py` |

```console
$ export VERITAS_REGISTRY_PATH=C:/Projects
$ export VERITAS_PREDICATE_SEMANTICS_PATH=C:/G1/tools
$ export VERITAS_WRITEBACK_VALIDATOR_PATH=C:/G1/tools
$ export VERITAS_OUTCOME_TAXONOMY_PATH=C:/G1/tools
$ export VERITAS_CAPABILITY_INVENTORY_PATH=C:/G1/tools

$ veritas-demo doctor
Veritas capability load
  [ok  ] capability_inventory   AVAILABLE
  [ok  ] outcome_taxonomy       AVAILABLE
  [ok  ] predicate_semantics    AVAILABLE
  [ok  ] registry               AVAILABLE
  [ok  ] writeback_validator    AVAILABLE
  complete: True
```

Resolution order is explicit and always reported: environment variable, then an
already-importable module, then the (empty by default) `search_paths` list in
`veritas_demo/veritas.providers.json`.

**If a capability is missing, Veritas says so and refuses to guess.** It never
substitutes a built-in approximation, and it never exits 0 while unable to
answer:

```console
$ veritas-demo doctor          # with no bindings configured
  [MISS] registry               UNAVAILABLE
         source=unresolved sys.path: ModuleNotFoundError: No module named 'state_registry'
  complete: False
$ echo $?
2

$ veritas-demo admit --scenario legitimate
{
  "capability": "UNAVAILABLE",
  "description": "A claim that holds up under every gate.",
  "evaluated": false,
  "exit_code": 2,
  "scenario": "legitimate",
  "verdict": "UNAVAILABLE"
}
$ echo $?
2
```

Note that the `legitimate` scenario does **not** come back `ADMITTED` when the
validator is missing. An absent gate is not a passing gate.

## Exit codes

Two things are reported separately, because conflating them is a defect in
either direction:

- **Command execution status** — did Veritas perform the requested evaluation?
  This is the process exit code.
- **Domain verdict** — what did the upstream capability decide? This is data in
  the output and never moves the exit code.

So a governed `REFUSED` is a *successful evaluation* and exits 0. Only an
unavailable capability, a malformed invocation, or a failed assertion is
non-zero.

| Code | Meaning |
|---:|---|
| 0 | the requested evaluation completed |
| 2 | a required upstream capability was unavailable |
| 3 | an expected behavioral assertion did not hold (`selftest` only) |
| 64 | the invocation was malformed |

| Command | Required capability | exit 0 when | exit != 0 when |
|---|---|---|---|
| `doctor` | — | every declared capability resolved | one or more unresolved |
| `find` | `capability_inventory` | the query executed | inventory unavailable |
| `predicates` | `predicate_semantics` | lattice loaded and rendered | provider unavailable |
| `outcomes` | `outcome_taxonomy` | taxonomy loaded and rendered | provider unavailable |
| `admit` | `writeback_validator` | the scenario was evaluated, **including a legitimate `REFUSED`** | validator unavailable |
| `provenance` | `registry` | the requested check executed, **even if the policy refuses** | registry unavailable |
| `selftest` | `writeback_validator` | every expected assertion held | an assertion failed, or validator unavailable |

`find` is worth a note: `NO_MATCH`, `PARTIAL_MATCH` and `MULTIPLE_CANDIDATES`
are domain verdicts that exit 0. `NO_MATCH` describes the index that was
searched, not the world — the upstream wording says so, and Veritas preserves
it rather than flattening it into absence.

Run `veritas-demo exit-codes` to print this table from the code that implements it.

## Run

```console
$ veritas-demo doctor                       # what resolved, and how
$ veritas-demo find "resource-aware placement"
$ veritas-demo predicates                   # the 24-predicate strength lattice
$ veritas-demo outcomes                     # how attempts are classified
$ veritas-demo admit                        # all six admission scenarios
$ veritas-demo admit --scenario invent-predicate
$ veritas-demo provenance --demo            # policy gate + hash chain
$ veritas-demo selftest                     # each scenario refuses for the right reason
```

Every command takes `--text` for human-readable output and emits JSON by
default, so the same CLI works in a terminal and in a script.

```console
$ veritas-demo admit --scenario escalate-identity --text
[             REFUSED] escalate-identity  Assert that a file path establishes a concept identity.
     refused: IDENTITY_ESCALATION on src/router.py --DEFINES_CONCEPT--> congestion_control
```

## Test

```console
$ python -m pytest -q
55 passed
```

The suite asserts that the adapter delegates correctly and that each scenario is
refused **for its documented reason** — not merely that it is refused. It skips
individual tests when a capability is unavailable rather than reimplementing the
behaviour locally. It pins both dimensions separately: a governed `REFUSED`
exits 0, an unavailable capability exits non-zero, and neither may be inferred
from the other. `test_exit_code_never_encodes_a_domain_verdict` is the guard
test — it asserts the derivation cannot read a verdict field in either
direction.

With no capabilities bound the suite degrades rather than fails:

```console
$ python -m pytest -q
25 passed, 36 skipped
```

---

## The scenarios

Each one is a real way a claim goes wrong, and each is refused by name.

| Scenario | Proposal | Outcome |
|---|---|---|
| `legitimate` | add a location fact for a file already known to implement a concept | `ADMITTED` |
| `inflate-correlation` | restate an observed association as `CAUSES` | `REFUSED` — `CAUSATION_FROM_CORRELATION` |
| `escalate-identity` | claim a path `DEFINES_CONCEPT` | `REFUSED` — `IDENTITY_ESCALATION` |
| `escalate-ownership` | claim `OWNED_BY_OPERATOR` from a location fact | `REFUSED` — `OWNERSHIP_ESCALATION` |
| `invent-predicate` | introduce `VIBES_WITH` | `REFUSED` — `UNREGISTERED_PREDICATE` |
| `weakening-loss` | downgrade `CAUSES` to `ASSOCIATED_WITH` | `ADMITTED_WITH_LOSS` — `ADMISSIBLE_WEAKENING` |

The last one is the interesting case. Making a claim *weaker* is allowed, but it
is recorded as a loss rather than passing silently. A system that only ever says
no is not trustworthy; one that records what it gave up is.

---

## Known limits

- The upstream `predicate_semantics` vocabulary is domain-specific to that
  estate. `CAUSES` and `OWNED_BY_OPERATOR` mean what they mean there. Veritas
  surfaces the lattice; it does not claim the vocabulary is universal.
- `state_registry` requires `new_experiment` and `reopening` to be
  `OperationPolicy` objects, not bare `OperationLevel` values. Veritas's
  `register_component` handles this so callers do not have to.
- Chain verification covers each component's `history` records. Component fields
  outside that list are not covered by the chain; Veritas does not claim
  otherwise.
- `capability_inventory` reads a live concept corpus from its own estate. When
  that corpus is not present it returns `NO_MATCH`, which is an honest
  *not-found-here*, not a global absence.

## License

**ADAPTER-ONLY. Upstream licensing unresolved.** Veritas' own code is MIT.
It redistributes none of the upstream capabilities, the G1 concept corpus, or
any other internal payload, and binds to operator-provided copies at runtime.

The upstream capabilities it binds to carry **no license file**, and none is
published on PyPI. What was established:

| Upstream | Author provenance | Third-party content | License file |
|---|---|---|---|
| `state_registry` | 17 commits, single identity `UrukuTelal`, remote `UrukuTelal/state_registry` | **none** — stdlib only across the whole package | never existed, in any commit |
| `predicate_semantics` | **no VCS** — `C:\G1` is not a git repository | **none** — stdlib only | none anywhere |
| `writeback_validator` | no VCS | **none** — stdlib + one operator-authored sibling | none anywhere |
| `outcome_taxonomy` | no VCS | **none** — zero imports of any kind | none anywhere |
| `capability_inventory` | no VCS | **none** — stdlib only | none anywhere |

No vendored subtree, no lifted standards text, no copyleft dependency. So
**nothing here redistributes upstream source**, and publishing this repository
requires no grant from anyone.

What remains open is narrower than "is it licensed": **there is no durable
right to depend on these modules**, because absent a license they are
all-rights-reserved by default. That costs nothing today and would matter the
moment Veritas vendors a file, quotes a paragraph, or ships a frozen copy.

### Distribution shape

**Adapter-only.** Veritas reproduces none of the five upstream modules and none
of the G1 concept corpus. Self-contained bundling is **prohibited** until
upstream licensing is explicitly settled. Veritas grants no rights in upstream
code, and no license was added to any upstream project as part of this
decision. See `LICENSE` and `docs/LICENSING.md`.

## See also

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — cross-repo dependency map
- [`docs/PROVENANCE.md`](docs/PROVENANCE.md) — what is copied, what is bound
- [`docs/LICENSING.md`](docs/LICENSING.md) — upstream ownership, third-party content, open decision
- [`docs/DEMO-NOTES.md`](docs/DEMO-NOTES.md) — how each command was verified
