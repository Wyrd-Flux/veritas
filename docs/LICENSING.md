# Licensing

Recorded 2026-09-30. Updated for the public-core migration.

## Short answer

| Component | License | Where |
|---|---|---|
| Veritas | **MIT** | [`LICENSE`](../LICENSE) |
| `wyrd-evidence-core` | **Apache-2.0** | its own `LICENSE`, at its own repository |

Veritas depends on the evidence core through ordinary packaging. Nothing private
is redistributed by either repository.

## The change, and why it was necessary

Veritas 0.1.0 was published adapter-only: it bound to internal source trees at
runtime via `VERITAS_<NAME>_PATH` and redistributed none of them. That was a
defensible reading of "publish nothing you cannot license", and it produced a
repository that **nobody without the private estate could run** — including the
people a public demo exists for.

The operator resolved this on 2026-09-30 by licensing the extracted public work
explicitly (D1: Apache-2.0) and directing that both demos depend on it normally
(D4: GitHub-only distribution in this phase).

## What the migration did and did not do

**Did:** extract the four self-contained evidence modules into
`wyrd-evidence-core`, and record their source paths and SHA-256 hashes in that
package's `docs/PROVENANCE.md`.

**Did not:** add, modify, or remove a license in any internal source repository.
`Ollama_Controller`, `state_registry` and the `C:\G1\tools` trees remain
unlicensed and unmodified. The Apache-2.0 grant covers the extracted public work.

**Did not:** fabricate history. Three of the extracted modules had no version
control at source. That is recorded as `NO_VCS_HISTORY_AT_SOURCE` in both the
evidence core's provenance and Veritas' `LICENSE`, rather than being papered over.

## Operator attestation

> The modules `predicate_semantics.py`, `writeback_validator.py`, and
> `outcome_taxonomy.py` were produced under my direction as part of this
> architecture. Their lack of Git/VCS history is a provenance deficiency, not
> evidence that they are third-party code.

Attested by `UrukuTelal` on 2026-09-30.

## Third-party material

None. The extracted modules import only the Python standard library. No vendored
subtrees, no embedded copyright headers, no copyleft dependency, so no
third-party terms flow through either repository.

The one dependency Veritas has is `wyrd-evidence-core`, which is Wyrd Flux's own
public work under Apache-2.0.

## Why Apache-2.0 for the core, and MIT for Veritas

Apache-2.0 was chosen for the core because it is intended as reusable
infrastructure: permissive reuse, plus an explicit patent grant and a
contribution-licence clause, which matter for a library others will build on.

Veritas is a demo rather than a library, and remains MIT. The asymmetry is
deliberate — the code meant to be depended upon gets the stronger grant.

## Not published

| Not shipped | Licensing consequence |
|---|---|
| the 61-concept G1 graph | private estate data; never published |
| internal `capability_inventory.py` | structurally requires that graph |
| any `C:\G1` or `C:\Projects` path | must not travel with the code |

Nothing in either repository is licensed that was not extracted deliberately, and
nothing extracted is left unlicensed.

## Verifying

```console
$ pip show wyrd-evidence-core     # Apache-2.0, per its own LICENSE
$ git log --oneline               # history preserved; migration was a new commit
```

Veritas' git history was not rewritten. The adapter-only release remains in the
history, so the earlier decision and its reversal are both auditable.
