# Architecture

Veritas is a small application over four evidence primitives from one installed
package, plus a capability-discovery layer it owns. This document records where
each boundary falls and why.

## The composition

```
                    ┌──────────────────────────────────────────┐
                    │           veritas_demo.cli               │
                    │  doctor · find · predicates · outcomes ·  │
                    │  admit · provenance · selftest            │
                    └──────┬──────────────────────────┬────────┘
                           │                          │
        ┌──────────────────▼───────────┐   ┌──────────▼─────────────────┐
        │      veritas_demo.core       │   │  veritas_demo.capabilities│
        │  VeritasSession              │   │  CapabilityRegistryProvider│
        │  builds inputs, unpacks      │   │  LocalJsonRegistryProvider │
        │  upstream results            │   │  search() over N providers │
        │  NO policy of its own        │   │  bundled synthetic example │
        └──────────────┬───────────────┘   └────────────────────────────┘
                       │ import
        ┌──────────────▼───────────────────────────────────────────────┐
        │            wyrd-evidence-core  (Apache-2.0)                   │
        │                                                                │
        │  predicate_semantics   the strength lattice, 24 predicates    │
        │  writeback_validator   relation-set admission                 │
        │  outcome_taxonomy      10 classes in 4 families               │
        │  registry              component state, policy, hash chain    │
        └────────────────────────────────────────────────────────────────┘
```

## What is delegated, and to where

| Veritas operation | Delegates to | Decides |
|---|---|---|
| `predicates` | `predicate_semantics` | predicate strength, directionality, powers |
| `admit` | `writeback_validator` | accept / refuse / admissible-loss, with reason codes |
| `outcomes` | `outcome_taxonomy` | which family an outcome class belongs to |
| `provenance` | `registry` | state transitions, the policy gate, chain validity |
| `find` | **nothing** — it is Veritas' own | lexical candidate leads |

The first four return upstream's own answers. Veritas builds the inputs and
renders the outputs, and changes neither.

## The one thing Veritas owns

`capabilities.py` exists because the internal capability inventory it replaced
was coupled to a private corpus, and the useful part of it — *"a lexical match is
a candidate lead"* — has nothing to do with evidence semantics. Putting it in
`wyrd-evidence-core` would have made the evidence library carry capability-search
vocabulary it has no use for.

It is ~450 lines and depends on nothing but the standard library, which is the
condition for it being obviously separable later if a second consumer appears.

### The provider seam

```python
class CapabilityRegistryProvider(Protocol):
    name: str
    def load(self) -> list[CapabilityRecord]: ...
```

`find` takes a *list* of providers, not a registry path. v1 ships one
implementation — `LocalJsonRegistryProvider`, a JSON file — but the search and
output code never names it. A URL registry, a package entry point, or a
private-estate adapter is a new class, not a rewrite.

Two rules govern registry selection, and both exist because the failure they
prevent is silent:

1. **Precedence is not merging.** Supplying `--registry` or
   `VERITAS_CAPABILITY_REGISTRY` replaces the bundled example; it does not add to
   it. A caller who points at their own registry means it, and silently mixing in
   demo data would corrupt the answer.
2. **An unreadable registry raises.** It does not fall back. A mistyped path must
   not be able to look like a genuine capability gap — which is why
   `REGISTRY_UNAVAILABLE` exits non-zero while `NO_MATCH` exits zero.

## Three failure modes this package is built to avoid

**Local substitution of a governed rule.** Veritas must never answer with its own
approximation of an evidence decision. Concretely: `core.py` contains no
`except ImportError`, no `if module is None`, and no `hasattr(module, ...)`. A
missing dependency stops the program at import, loudly. Enforced by
`test_no_local_substitution_of_a_governed_rule`.

**Silent regression to a source-tree binding.** A contributor could reintroduce a
private-module import without noticing. `test_veritas_names_no_private_estate_module`
scans every source file for any reference to a private module name, whether by
import or by attribute access.

**Absence read as prohibition.** Three places enforce the opposite convention,
because each was a real defect:

| Behaviour | Why |
|---|---|
| `unknown != forbidden` in the registry | a missing registration must not look like a policy decision |
| `NO_MATCH` means "not in the registries searched" | a registry may be incomplete |
| an unreadable registry is not `NO_MATCH` | a failure to answer is not an answer |

## Layering rules this codebase follows

- **No governed policy in Veritas.** No predicate strength, no refusal code, no
  admissibility rule. Those belong to `wyrd-evidence-core` and are not duplicated.
- **No source-tree binding.** No `sys.path` manipulation, no environment
  variables for capability loading, no provider-resolution layer. The dependency
  graph is what `pyproject.toml` declares, and a test holds the source to it.
- **No private corpus.** The only registry shipped is synthetic, labelled, and
  uses `EXAMPLE_`-prefixed ids.
- **Ranking is never a recommendation.** `find` carries the caveat in its data,
  not only in its help text.
- **Exit codes separate execution from verdict.** A refusal exits 0; a failure to
  answer does not.

## Registry format

Small on purpose, and extensible:

```json
{
  "registry": "my-team",
  "version": "1",
  "capabilities": [
    {
      "id": "TEAM_METRICS_PIPELINE",
      "name": "metrics pipeline",
      "description": "...",
      "terms": ["metrics", "pipeline"],
      "aliases": ["telemetry"],
      "status": "implemented",
      "source": "https://github.com/my-org/metrics",
      "callable": true,
      "evidence_notes": "covered by integration tests",
      "verification": ["tests/test_ingest.py"],
      "anything_else_you_like": {"kept": "in record.extra"}
    }
  ]
}
```

Only `id` is required. Unknown fields are preserved rather than rejected, so the
schema can grow without a version negotiation.

### Matching

Terms are matched as **whole words**, never as substrings. A single incidental hit
is treated as noise: a candidate is only reported once at least
`MIN_SIGNIFICANT_TERMS` distinct query terms match, and the default of 2 is a
floor rather than a scoring nicety.

That floor exists because an earlier version scored a nonsense query at 0.10
against unrelated prose, which made `NO_MATCH` unreachable. A surface whose
refusal cannot be reached is broken, whatever its precision.
