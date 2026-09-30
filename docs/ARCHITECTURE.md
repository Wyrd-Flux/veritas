# Architecture

Veritas is a thin application over five capabilities that already exist in
three different source trees. This document records exactly what it depends on
and where the boundaries fall.

## The composition

```
                        ┌──────────────────────────────────────┐
                        │            veritas_demo.cli          │
                        │  doctor · find · predicates ·        │
                        │  outcomes · admit · provenance ·     │
                        │  selftest                            │
                        └───────────────┬──────────────────────┘
                                        │
                        ┌───────────────▼──────────────────────┐
                        │           veritas_demo.core          │
                        │  VeritasSession                      │
                        │  CapabilityStatus / EdgeVerdict      │
                        │  find_capability · predicate_lattice │
                        │  admit_edges · outcome_classes       │
                        │  open_registry · policy_gate         │
                        │  verify_provenance                   │
                        └───────────────┬──────────────────────┘
                                        │  ProviderSet.require(capability)
                        ┌───────────────▼──────────────────────┐
                        │      veritas_demo.providers          │
                        │  resolution order + explicit report  │
                        │  1. VERITAS_<NAME>_PATH              │
                        │  2. importable module on sys.path    │
                        │  3. search_paths (empty when shipped)│
                        └───────────────┬──────────────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
┌───────▼─────────┐          ┌──────────▼─────────┐         ┌──────────▼─────────┐
│  C:/Projects    │          │     C:/G1/tools    │         │     C:/G1/tools    │
│                 │          │                     │         │                     │
│ state_registry  │          │ predicate_semantics │         │ writeback_         │
│                 │          │                     │         │   validator        │
│ · schema.py     │          │ 24 predicates       │         │                     │
│ · registry.py   │          │ 6 strength classes  │         │ 13 refusal codes   │
│ · contradiction │          │ oriented / temporal │         │ before→after gate  │
│   .py           │          │   policies          │         │                    │
└─────────────────┘          └─────────────────────┘         └────────────────────┘
                                       │                               │
                        ┌──────────────▼─────────┐         ┌──────────▼─────────┐
                        │     C:/G1/tools       │         │    C:/G1/tools     │
                        │ outcome_taxonomy      │         │ capability_        │
                        │ 10 classes in 3 fams  │         │   inventory        │
                        └───────────────────────┘         └────────────────────┘
```

Two source trees, five independently-built capabilities, one application.

## The five capabilities in detail

### `registry` — `state_registry`

Owns: component disposition, per-operation policy, hash-chained history.

| Upstream surface | Used for |
|---|---|
| `state_registry.registry.StateRegistry` | open / persist a registry |
| `.register(ComponentState)` | declare a component |
| `.transition(name, Disposition, ...)` | move it through a disposition |
| `.can_modify(name, op)` | the policy gate; returns `(permitted, reason, required_authority)` |
| `.verify_history(name)` | verify the `prev_hash`/`hash` chain |
| `.verify_provenance(name)` | resolve declared evidence references |
| `state_registry.schema.*` | `ComponentState`, `State`, `Policy`, `OperationPolicy`, `OperationLevel`, `Authority`, `Disposition`, `ResearchState` |

Veritas additionally binds (not yet exposed as a subcommand):

- `state_registry.contradiction` — parses prose claims out of a document and
  diffs them against recorded state, reporting `info` / `conflict` severity.
  This is the natural companion to `provenance` and the most likely next
  subcommand.
- `state_registry.ci_check.run_ci_check()` / `state_registry.precommit.run_preflight()`
  — the same gate as a CI step and as a pre-commit hook.

### `predicate_semantics` — the strength lattice

Owns: 24 predicates, 6 strength classes (`CORRELATIONAL` → `AUTHORITY`),
directionality, temporal policy, and which predicates may establish identity,
ownership, or causation.

Veritas renders it; it adds no predicates.

Two invariants the demo leans on, both asserted in `tests/test_veritas.py`:

- exactly `OWNED_BY_CONCEPT` and `OWNED_BY_OPERATOR` grant ownership
- exactly `CAUSES`, `MOTIVATES` and `RESOLVES` imply causation

### `writeback_validator` — the admission gate

Owns: comparing a proposed relation set against the current one. Returns
accepted, refused (13 named codes), and admissible losses.

Veritas translates the result into one of three verdicts plus the upstream
reason codes:

| Upstream result | Veritas verdict |
|---|---|
| nothing refused, nothing lost | `ADMITTED` |
| nothing refused, losses present | `ADMITTED_WITH_LOSS` |
| one or more refused | `REFUSED` |

### `outcome_taxonomy` — how attempts end

Owns: 10 classes in 3 families (`RESOLVED`, `REFUSED`, `OPEN`) plus
`summarise()` / `render()`.

### `capability_inventory` — the discovery surface

Owns: mapping a stated need to registered systems, with an evidence qualifier
per candidate (`CALLABLE`, `NOT_CALLABLE`, …) and a next-action string.

Veritas passes the verdict through. It does not re-rank candidates — deciding
which one to read is the caller's judgement, and pretending otherwise would
reintroduce exactly the drift this capability exists to prevent.

## Why these five and not others

The estate contains substantially larger subsystems — a 1,621-test inference
controller with resource-aware placement, an FMM fast-multipole solver, a
constraint-guided life simulation, an adaptive vector compressor. Veritas was
built from the five smallest ones because:

1. **They run with no GPU, no model server, and no network.** The demo is
   reproducible on a laptop, which the larger systems are not.
2. **Their decisions are pure.** Same input, same verdict, byte-identical hash.
   That makes the refusals reproducible in a test rather than anecdotal.
3. **They compose into one question.** Discovery → claim → admission →
   classification is a single thread. The larger subsystems each answer a
   different question and would not have cohereed.
4. **Their refusals are named.** A refusal code is checkable. "The system said
   no" is not.

## Layering rules this codebase follows

- **No decision logic lives in Veritas.** `core.py` builds upstream inputs and
  unpacks upstream results. Every verdict and every refusal code originates
  upstream.
- **No silent substitution.** A missing capability produces `UNAVAILABLE` and a
  non-zero exit, never a local approximation. Four tests pin this.
- **No upstream import at module scope.** All five are resolved lazily through
  `ProviderSet`, so `import veritas_demo` works with nothing installed.
- **No machine-specific paths in version control.** The shipped
  `veritas.providers.json` has an empty `search_paths`. Bindings come from the
  environment.
- **No writes outside the caller.** `open_registry()` with no argument uses a
  fresh temporary directory. The demo never writes into an upstream corpus.
