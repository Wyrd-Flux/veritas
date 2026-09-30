# Source provenance

Veritas was assembled from an existing estate. This records exactly what came
from where, and — more importantly — what did **not** come from anywhere.

Recorded 2026-09-30.

## Upstream sources

These are **source trees** — where the implementations live. They are not the
values to supply to `VERITAS_<NAME>_PATH`, which take the directory to place on
`sys.path`. For `registry` that is `C:/Projects`, the parent of
`C:/Projects/state_registry`; see the README bindings table.

| Capability | Source tree | Files used | Written by |
|---|---|---|---|
| `registry` | `C:/Projects/state_registry` | `registry.py`, `schema.py` | the estate's state-registry workstream |
| `predicate_semantics` | `C:/G1/tools` | `predicate_semantics.py` | the estate's evidence-governance workstream |
| `writeback_validator` | `C:/G1/tools` | `writeback_validator.py` | same workstream |
| `outcome_taxonomy` | `C:/G1/tools` | `outcome_taxonomy.py` | same workstream |
| `capability_inventory` | `C:/G1/tools` | `capability_inventory.py` | same workstream |

Git metadata for both trees is externalised to `C:/LocalGitDirs/`, so a
`.git` file in either root points at a gitdir rather than containing history.

## What was copied: nothing

Veritas contains **zero lines** of upstream code. It contains:

| File | Role |
|---|---|
| `veritas_demo/providers/__init__.py` | capability resolution, import, reporting |
| `veritas_demo/core.py` | `VeritasSession`; builds upstream inputs, unpacks upstream results |
| `veritas_demo/cli.py` | argument parsing, output rendering, scenario definitions |
| `veritas_demo/__main__.py` | module entry point |
| `veritas_demo/__init__.py` | public re-exports |
| `veritas_demo/veritas.providers.json` | empty search-path list + documentation |
| `tests/test_veritas.py` | 38 conformance tests |
| `pyproject.toml`, `README.md`, `docs/*`, `LICENSE` | packaging and documentation |

The scenario definitions in `cli.py` are *test fixtures describing claims*, not
code lifted from anywhere. Each is a subject/predicate/object triple plus its
evidence ref.

## What was deliberately not done

**No vendoring.** Upstream modules are imported at runtime. If
`state_registry` is absent, `veritas-demo doctor` reports `UNAVAILABLE` and
exits non-zero. It does not carry a fallback copy.

**No reimplementation.** There is no local edge validator, no local predicate
table, no local hash-chain implementation. Every verdict printed by this
application was produced by the upstream module that owns that decision.

**No patching upstream at the call site.** Veritas constructs upstream types
directly (`ComponentState`, `OperationPolicy`, `Edge`) rather than
duck-typing. This means a breaking upstream change surfaces immediately as a
`TypeError` or `AttributeError` rather than as silently wrong behaviour — the
failure mode the upstream code is written to avoid.

## Two adaptations, and why

Both are documented in the code where they occur.

### 1. `Policy.new_experiment` and `Policy.reopening` are `OperationPolicy`

Upstream `schema.Policy` accepts `OperationLevel` for these fields at
construction but calls `.level.value` when serialising, so a bare
`OperationLevel` raises `AttributeError` on `register()`. Veritas's
`register_component` wraps them:

```python
new_experiment=schema.OperationPolicy(level=schema.OperationLevel.ALLOWED),
reopening=schema.OperationPolicy(
    level=schema.OperationLevel(reopening_level), reason=reopening_reason
),
```

This is an upstream constructor/serialiser mismatch. Veritas works around it at
the call site instead of patching upstream, so the workaround is visible and
removable. **Worth reporting upstream.**

### 2. `transition()` takes `Disposition` members, not strings

Veritas passes `schema.Disposition.PRESERVE` rather than `"PRESERVE"`. Cosmetic,
but recorded because passing a string is the obvious first thing to try and it
fails.

## Upstream behaviour Veritas deliberately does not claim

Two findings from verifying the upstream engines. Neither is a Veritas bug; both
are limits on what this demo can honestly assert, and both are stated in the
README.

**Chain scope.** `verify_history` covers each component's `history` records.
Editing a component field that sits outside that list — `established_by`, for
example — does not invalidate the chain, and loading succeeds. Veritas does not
present "chain valid" as "component unaltered."

**`new_experiment` is not consulted by the disposition gate.** For an `OPEN`
component every operation is permitted regardless of the per-operation policy,
because the disposition-level branch returns before reaching it. This is
documented in the upstream `can_modify` docstring and appears to be intended. It
is recorded here because a reader could reasonably expect `PROHIBITED` to win
against `OPEN`.

## Licensing status

Full analysis in [`LICENSING.md`](LICENSING.md). Summary:

Veritas' own code is MIT. **No upstream source is redistributed.** Verified:

```console
$ grep -rnE "class (Edge|Predicate|StateRegistry|ComponentState|Disposition|Verdict|OperationPolicy)\b" veritas_demo/
$ # no matches
```

`state_registry` has 17 commits under a single identity (`UrukuTelal`), remote
`github.com/UrukuTelal/state_registry`, and **no LICENSE has ever existed in
any commit**. `C:\G1` is not a git repository at all, and the four modules
Veritas binds from it are unversioned, unlicensed, and unattributed.

All five are **stdlib-only** (`outcome_taxonomy` has zero imports of any kind;
`writeback_validator` adds one operator-authored sibling). No vendored subtree,
no copyleft dependency, no lifted standards text. So no third-party terms flow
through and there is no transitive license surface.

Consequences, stated plainly:

- Veritas imports these modules at runtime and **redistributes none of them**.
  Publishing Veritas does not publish them, and needs no grant from anyone.
- Anyone running the demo uses their own copy of the upstream trees.
- The four `C:\G1` modules have **no VCS provenance at all**. Root 1 does.
- The `C:\G1` concept corpus is **not bundled**, so `find` degrades to a
  reported `NO_MATCH` when it is absent.

**Distribution shape: ADAPTER-ONLY (operator decision, 2026-09-30).** Veritas
reproduces none of the five upstream modules and none of the G1 concept corpus.
**Self-contained bundling is prohibited** until upstream licensing is explicitly
settled. Veritas grants no rights in upstream code, and no license was added to
any upstream project as part of this decision.

**Still open:** absent a license, these modules are all-rights-reserved by
default. Veritas has no durable right to depend on them — it simply copies
nothing out. Full analysis in [`LICENSING.md`](LICENSING.md).

## Verifying these claims

```console
$ veritas-demo doctor
```

`doctor` prints, for each capability, the module name and the resolution source
it came from. That is the receipt for the whole of this document.

To confirm no upstream code was copied:

```console
$ grep -rE "class (Edge|Predicate|StateRegistry|ComponentState)\b" veritas_demo/
$ # no matches
```
