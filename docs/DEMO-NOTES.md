# Demo notes

Recorded 2026-09-30, for reviewers who want to know which claims were executed
rather than argued.

## Environment

| | |
|---|---|
| Python | 3.11 |
| Dependency | `wyrd-evidence-core` 0.1.0 from GitHub |
| Private estate | **not required, and not consulted** |

Nothing here needs a GPU, a model, or a network. Veritas is entirely local, which
is why its acceptance test is stricter than Placement Gate's.

## Acceptance: the six-step `find` walkthrough

Every step below was executed from a clean clone in a fresh virtualenv.

**1 — install from a clean clone**

```console
$ git clone https://github.com/Wyrd-Flux/veritas
$ cd veritas
$ python -m venv .venv
$ .venv/bin/pip install .
```

Resolved `wyrd-evidence-core` from GitHub. No `VERITAS_*` variable was set, and no
`C:\G1` or `C:\Projects` path existed on `sys.path`.

**2 — `find` against the bundled synthetic registry**

```console
$ veritas-demo --text find "evidence verification audit"
verdict   : PARTIAL_MATCH
candidates (lexical leads, not recommendations):
  EXAMPLE_EVIDENCE_VERIFICATION  [implemented]  score=1.0  terms=audit,evidence,verification
exit=0
```

**3 — candidate leads received, with the caveat attached**

The output carries the source registry, the matched terms, and the sentence that
ranking is not a recommendation.

**4 — point `find` at a user-created registry**

```console
$ veritas-demo --text find "metrics pipeline ingest aggregate" --registry ./mycap.json
verdict   : PARTIAL_MATCH
candidates (lexical leads, not recommendations):
  TEAM_METRICS_PIPELINE  [implemented]  score=1.0  terms=aggregate,ingest,metrics,pipeline
exit=0
```

The bundled example was **not** searched alongside it. Precedence is replacement,
not merging.

**5 — results come from that registry**

`registries: mycap.json`. The lead id came from the user's file, not from Veritas.

**6 — remove the registry**

```console
$ mv mycap.json mycap.json.bak
$ veritas-demo --text find "metrics pipeline ingest aggregate" --registry ./mycap.json
verdict: REGISTRY_UNAVAILABLE
detail : registry 'mycap.json': cannot read .../mycap.json: No such file or directory

no fallback registry was searched. Point --registry at a readable
capability registry, or unset it to use the bundled example.
$ echo $?
2
```

Non-zero, and **nothing was searched**. It did not fall back to the example. A
typo in a path cannot masquerade as a capability gap.

**7 — no private concept graph in the wheel or repo**

```console
$ grep -c . veritas_demo/example_capability_registry.json   # the only registry shipped
1
```

Every id in it begins `EXAMPLE_`, the document carries `"synthetic": true`, and
`_note` states in the file itself that none of it describes real software.
`test_no_private_concept_graph_is_present_anywhere` enforces this.

## Exit-code separation, verified

```console
$ veritas-demo admit --scenario inflate-correlation >/dev/null; echo $?
0                                  # REFUSED, and that is a correct answer
$ veritas-demo find "anything" --registry ./nope.json >/dev/null; echo $?
2                                  # could not ask the question
$ veritas-demo --nonsense >/dev/null 2>&1; echo $?
64                                 # a typo
```

`NO_MATCH` also exits 0, because a completed search that finds nothing is a
completed search. Only a failure to answer moves the exit code.

## The six admission scenarios

All ship with the demo and are asserted by `selftest`:

| Scenario | Expected | What it tests |
|---|---|---|
| `inflate-correlation` | `REFUSED` | causation cannot be claimed from a correlational predicate |
| `escalate-identity` | `REFUSED` | a path reference cannot establish identity |
| `escalate-ownership` | `REFUSED` | a path reference cannot establish ownership |
| `invent-predicate` | `REFUSED` | an unregistered predicate is refused, not defaulted |
| `weakening-loss` | `ADMITTED_WITH_LOSS` | losing a claim is admissible, and is recorded |
| `legitimate` | `ADMITTED` | the control: a supported relation is admitted |

```console
$ veritas-demo selftest
  [PASS] inflate-correlation  REFUSED  [...]
  [PASS] escalate-identity     REFUSED  [...]
  ...
  selftest passed
$ echo $?
0
```

## Provenance verified

```console
$ veritas-demo --text provenance --demo
registered ROUTER
  gate(OPEN, implementation): True - Component ROUTER is OPEN: all operations permitted
  chain valid: True  records: 1
  gate(NEVER_REGISTERED, implementation): True - Component not in registry (unknown != forbidden)
```

Chain tampering is detected in the test suite, so `chain valid: True` is a claim
with teeth rather than a formality.

## What was **not** verified

- **No URL registry, no entry-point registry, no G1 adapter.** The provider
  protocol exists so they can be added; none is implemented or claimed.
- **Matching is lexical.** No synonyms, no embeddings, no semantic search. An
  earlier internal version said the same thing and it is still the limit.
- **Single-user, single-process.** Nothing here is tested under concurrent
  registry writers.
- **No claim about your estate.** `find` says what it searched. If your registry
  is incomplete, so is the answer, and the output says so.

## Reproducing

```console
$ git clone https://github.com/Wyrd-Flux/veritas
$ cd veritas
$ python -m venv .venv
$ .venv/bin/pip install .
$ .venv/bin/python -m pytest -q
$ .venv/bin/veritas-demo doctor
$ .venv/bin/veritas-demo selftest
$ .venv/bin/veritas-demo find "evidence verification audit"
```

Expected:

```
76 passed
```
