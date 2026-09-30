# Veritas

**Most systems that talk about evidence never define what evidence *is*. Veritas
does — as a lattice, not as a comment — and then refuses the claims that lattice
does not support.**

This is a governed claim-admission demo. You propose a set of relations; Veritas
tells you which ones may be written, which are refused, and *why*. Every refusal
is decided by a typed evidence registry and reported with its own reason string.
Veritas adds no opinions and carries no fallback.

```console
$ veritas-demo --text admit --scenario inflate-correlation
[             REFUSED] inflate-correlation  Promote an observed association to a causal claim.
     refused: RELATION_TYPE_SUBSTITUTION on ROUTER --CAUSES--> latency_p99
     refused: RELATION_STRENGTHENING on ROUTER --CAUSES--> latency_p99
     refused: CAUSATION_FROM_CORRELATION on ROUTER --CAUSES--> latency_p99
$ echo $?
0
```

**That exit code is the point.** The command ran, and the answer is "no". A
governed refusal is a successful evaluation — see [Exit codes](#exit-codes).

---

## Contents

- [Install](#install)
- [Run](#run)
- [What it composes](#what-it-composes)
- [The evidence lattice](#the-evidence-lattice)
- [Governed relation admission](#governed-relation-admission)
- [Provenance you can verify](#provenance-you-can-verify)
- [find: capability discovery](#find-capability-discovery)
- [Exit codes](#exit-codes)
- [Tests](#tests)
- [License](#license)

---

## Install

```console
$ git clone https://github.com/Wyrd-Flux/veritas
$ cd veritas
$ python -m venv .venv
$ .venv/bin/pip install .
$ .venv/bin/veritas-demo selftest
```

That is the whole setup. No environment variables, no source-tree bindings, no
access to anything private, and nothing else to install.

```
veritas → Python stdlib
```

**No dependencies at all** (`dependencies = []`). The evidence primitives live in
[`veritas_demo/evidence/`](veritas_demo/evidence) — the lattice, the validator,
the taxonomy and the registry are files in this repository, not a package you
have to resolve first. Python 3.11 or newer, and that is the whole requirement.

---

## Run

```console
$ veritas-demo doctor          # what is available, and which registries find uses
$ veritas-demo predicates      # the evidence strength lattice
$ veritas-demo outcomes        # how an attempt is classified when it ends
$ veritas-demo admit --scenario inflate-correlation
$ veritas-demo provenance --demo
$ veritas-demo find "evidence verification"
$ veritas-demo selftest
$ veritas-demo exit-codes
```

`--text` renders human-readable output; JSON is the default.

---

## What it composes

| Capability | Where it lives | Question it answers |
|---|---|---|
| `predicate_semantics` | `veritas_demo/evidence/` | what does this evidence permit me to claim? |
| `writeback_validator` | `veritas_demo/evidence/` | may I write this relation set back over existing state? |
| `outcome_taxonomy` | `veritas_demo/evidence/` | how should this attempt be classified, given how it ended? |
| `registry` | `veritas_demo/evidence/` | what is this component's state, and can its history be verified? |
| capability discovery | `veritas_demo/capabilities.py` | has this already been built, anywhere I can search? |

The first four are the implementation, unmodified, and they bring their own
self-check suites: 24 predicate cross-checks, 11 verdict cases and 11
self-qualification cases, run by the test suite as the behavioural specification.
Veritas reimplements none of that behaviour and adds no opinions about any
refusal.

Capability discovery is Veritas' own because it needs a provider model the
evidence core has no business knowing about. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## The evidence lattice

Twenty-four predicates across six strength classes:

```console
$ veritas-demo --text predicates
```

The rule is an asymmetry:

- moving **down** the lattice is free — losing a claim is admissible loss
- moving **up** is strengthening, and it requires evidence
- standing still is free

And `get()` on an unregistered predicate **raises** rather than returning a
default. That is the load-bearing decision: a permissive fallback is how a
universal `RELATES_TO` primitive creeps back in, which is the exact failure a
typed evidence registry exists to prevent.

---

## Governed relation admission

```console
$ veritas-demo --text admit --scenario legitimate
$ veritas-demo --text admit --scenario invent-predicate
```

Six scenarios ship with the demo. Two are worth reading closely:

**`inflate-correlation`** — proposing `CAUSES` where the existing state only
supports `CORRELATES_WITH`. Refused twice: once for claiming causation from a
correlational predicate, once for strengthening without a token.

**`weakening-loss`** — proposing a *weaker* claim. Admitted, but recorded as an
`admissible_loss` rather than silently accepted. Losing information is allowed;
losing it invisibly is not.

The validator keeps two controls separate on purpose. `authorization` tokens
permit *strengthening*; `permitted_predicates` restricts *which relations may be
asserted at all*. A token that authorizes recording where something lives must
not also authorize declaring what that something **is**.

---

## Provenance you can verify

```console
$ veritas-demo --text provenance --demo
registered ROUTER
  gate(OPEN, implementation): True - Component ROUTER is OPEN: all operations permitted
  chain valid: True  records: 1
  gate(NEVER_REGISTERED, implementation): True - Component not in registry (unknown != forbidden)
```

Two details in that output are deliberate:

**`unknown != forbidden`.** Asking about a component that was never registered
returns *permitted*. Inventing a refusal would make absence look like a policy
decision, and would hide a component that was never registered.

**The chain is verifiable, not merely recorded.** Each history record carries a
`prev_hash`/`hash` pair, and tampering with any record makes verification fail.
Verification that cannot fail is not verification.

---

## find: capability discovery

`find` answers *"has this already been built?"* — and the honest answer is almost
never yes or no. It is a **candidate lead**: a lexical near-match worth looking at.

```console
$ veritas-demo --text find "evidence verification audit"
query     : evidence verification audit
verdict   : PARTIAL_MATCH
registries: example_capability_registry.json

candidates (lexical leads, not recommendations):
  EXAMPLE_EVIDENCE_VERIFICATION  [implemented]  score=1.0  terms=audit,evidence,verification
      source: https://github.com/Wyrd-Flux/veritas

note: Ranking reflects lexical term overlap with this registry's vocabulary. It is NOT
evidence that the capability satisfies the request, and NOT a recommendation.
```

### Your registry, not ours

A capability registry is a JSON document **you** supply:

```console
$ veritas-demo find "metrics pipeline ingest" --registry ./my-capabilities.json
```

```json
{
  "registry": "my-team",
  "version": "1",
  "capabilities": [
    {
      "id": "TEAM_METRICS_PIPELINE",
      "name": "metrics pipeline",
      "description": "Ingest and aggregate service metrics for dashboards.",
      "terms": ["metrics", "pipeline", "ingest", "aggregate"],
      "status": "implemented",
      "callable": true,
      "source": "https://github.com/my-org/metrics",
      "evidence_notes": "covered by integration tests",
      "verification": ["tests/test_ingest.py"]
    }
  ]
}
```

Every field is optional except `id`, and **unknown fields are preserved** rather
than rejected, so you can extend the schema without forking anything. Set
`VERITAS_CAPABILITY_REGISTRY` to select one without the flag.

### What the output does and does not claim

`find` carries three commitments, and the tests hold it to all three:

1. **A score is not a recommendation.** Ranking reflects lexical term overlap.
   Nothing more.
2. **`NO_MATCH` is not absence of proof.** It means *no query term appeared in
   the registries searched*. A registry may be incomplete, or may describe the
   capability in other words.
3. **An unreadable registry is not `NO_MATCH`.** It exits non-zero and searches
   nothing. A typo in `--registry` must not be able to masquerade as a genuine
   capability gap.

The bundled `example_capability_registry.json` is **synthetic demo data**,
labelled as such, with every id prefixed `EXAMPLE_`. It exists so `find` works
immediately after install. It describes no real Wyrd Flux software.

A URL registry, a Python package's entry points, or a private-estate adapter can
be added later — `find` searches a list of providers, and the local JSON provider
is just the first one.

---

## Exit codes

Execution status and domain verdict are separate. A governed refusal is a
completed evaluation.

| Code | Meaning |
|---:|---|
| 0 | the requested evaluation completed — **including a refusal** |
| 2 | a capability or configured registry was unavailable |
| 4 | a `selftest` assertion did not hold |
| 64 | the invocation was malformed |

```console
$ veritas-demo admit --scenario inflate-correlation >/dev/null; echo $?
0                                  # refused, and that is a correct answer
$ veritas-demo find "anything" --registry ./nope.json >/dev/null; echo $?
2                                  # could not ask the question
$ veritas-demo --nonsense >/dev/null 2>&1; echo $?
64                                 # a typo
```

`veritas-demo exit-codes` prints the full per-command contract from the code that
implements it.

---

## Tests

```console
$ python -m pytest -q
76 passed
```

Two of them matter more than the rest:

- **`test_veritas_names_no_private_estate_module`** tokenises every shipped
  file, discards comments and docstrings, and fails on any executable reference
  to a private module name. A regression to a source-tree binding fails the build.
- **`test_no_local_substitution_of_a_governed_rule`** asserts that `core.py`
  contains no `except ImportError`, no `if module is None`, and no
  `hasattr(module, ...)`. Veritas must not be able to quietly fall back to a
  local approximation of an evidence rule.

---

## License

**MIT** for Veritas. See [`LICENSE`](LICENSE).

The evidence primitives in `veritas_demo/evidence/` were originally extracted as
a separate Apache-2.0 package and are now folded in here. That history is
preserved rather than rewritten — see [`docs/PROVENANCE.md`](docs/PROVENANCE.md).
No private corpus, concept graph, or internal source tree is required or
shipped.

## See also

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — what is delegated where
- [`docs/PROVENANCE.md`](docs/PROVENANCE.md) — extraction record and history
- [`docs/DEMO-NOTES.md`](docs/DEMO-NOTES.md) — which claims were verified, and which were not
