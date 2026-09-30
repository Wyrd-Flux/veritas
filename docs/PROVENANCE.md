# Source provenance

Recorded 2026-09-30. This file records the migration as well as the original
provenance, because both matter to anyone reading the history.

## What Veritas depends on now

```
veritas
  └─ wyrd-evidence-core   (Apache-2.0, public, installed from GitHub)
       └─ Python standard library
```

That is the complete dependency graph. There is no source-tree binding, no
environment variable, and no private corpus.

`wyrd-evidence-core` was extracted from internal trees for this migration. Its
own [`PROVENANCE.md`](https://github.com/Wyrd-Flux/wyrd-evidence-core/blob/main/docs/PROVENANCE.md)
records the exact source paths and SHA-256 hashes. Veritas copies none of it.

## What Veritas contains

| File | Role |
|---|---|
| `veritas_demo/cli.py` | argument parsing, output rendering, scenario definitions |
| `veritas_demo/core.py` | `VeritasSession`; builds inputs, unpacks upstream results |
| `veritas_demo/capabilities.py` | **new** — the public capability-registry provider model |
| `veritas_demo/example_capability_registry.json` | **new** — synthetic demo registry |
| `veritas_demo/exit_codes.py` | the documented exit-code contract |
| `veritas_demo/__main__.py` | module entry point |
| `tests/test_veritas.py` | tests |

Zero lines of `wyrd-evidence-core` are copied here. The only thing Veritas adds is
capability discovery, which had to be written rather than extracted — see below.

## The migration (2026-09-30, this release)

**Before.** Veritas bound to four internal modules by path, at runtime, using
`VERITAS_<NAME>_PATH`, and to a fifth that read a private 61-concept graph:

| Old binding | Source tree |
|---|---|
| `registry` | `C:/Projects/state_registry` |
| `predicate_semantics` | `C:/G1/tools` |
| `writeback_validator` | `C:/G1/tools` |
| `outcome_taxonomy` | `C:/G1/tools` |
| `capability_inventory` | `C:/G1/tools` + `C:/G1/concepts` |

That design kept the redistributable surface at zero and therefore made the demo
**unrunnable for anyone without the private estate**. The demo's purpose is to be
run by people who do not have it, so the constraint was wrong.

**After.** Four capabilities are an ordinary dependency on
[`wyrd-evidence-core`](https://github.com/Wyrd-Flux/wyrd-evidence-core). The fifth
was replaced.

### Why `capability_inventory` was replaced, not published

It is structurally coupled to the private concept graph: `_load_concepts()` reads
61 JSON records from `C:\G1\concepts` with the path hardcoded at module level.
Shipping it would have meant shipping the graph, and shipping a 296 KiB private
corpus to preserve one command was the wrong trade.

The public design goal it was serving is real, though: *find out whether a
capability already exists.* So the surface was kept and the coupling removed:

| Internal | Public |
|---|---|
| hardcoded `C:\G1\concepts` | `--registry PATH`, `VERITAS_CAPABILITY_REGISTRY`, or a bundled synthetic example |
| `_load_concepts()` reading private JSON | `CapabilityRegistryProvider` protocol; v1 ships `LocalJsonRegistryProvider` |
| a fixed concept-record ontology | a small documented schema with unknown fields preserved |
| no way to say where a record came from | every result carries `source_registry` and `candidate_id` |

What was preserved is the lesson rather than the code: **a lexical match is a
candidate lead, not capability identity and not a recommendation**, and `NO_MATCH`
means "not in the registries searched", not "does not exist". The whole-word
matching rule and the `MIN_SIGNIFICANT_TERMS` floor came across unchanged, because
an earlier substring-matching version made `NO_MATCH` unreachable — and an
unreachable refusal is the one failure this surface exists to prevent.

The internal `capability_inventory.py` and the 61-concept graph remain internal,
unmodified and unpublished. A G1 adapter can be written later against the public
registry interface without G1 ever becoming a Veritas dependency.

## Provenance facts carried forward

**`NO_VCS_HISTORY_AT_SOURCE`** applies to the three modules from `C:\G1\tools`
(`predicate_semantics`, `writeback_validator`, `outcome_taxonomy`). That directory
is not under version control. No history was fabricated, in either the extraction
or this migration.

Operator attestation for those three modules is recorded in
`wyrd-evidence-core/docs/PROVENANCE.md`.

## Third-party material

None. `veritas_demo` imports only the standard library and `wyrd_evidence_core`.
No vendored directories, no embedded third-party code, no upstream headers.

## Licensing

- **Veritas:** MIT. See [`LICENSE`](../LICENSE).
- **wyrd-evidence-core:** Apache-2.0, by operator decision.

No license file was added to, or modified in, any internal source repository as
part of either the extraction or this migration. The internal trees remain
unlicensed; the grant covers the extracted public work only.

## What is deliberately absent

| Not shipped | Why |
|---|---|
| the 61-concept G1 graph | private estate data |
| `capability_inventory.py` | structurally requires the graph |
| any `C:\G1` or `C:\Projects` path | must not travel with the code |
| unrelated G1 tooling | nothing here depends on it |
| `state_registry/contradiction.py`, `ci_check.py`, `precommit.py` | repository-internal tooling, not the registry surface |
