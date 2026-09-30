# Source provenance

Recorded 2026-09-30, and updated twice: for the migration to a public core, and
then for folding that core back in. Both are recorded here, because both happened
and neither should disappear.

## What Veritas depends on

```
veritas → Python standard library
```

Nothing else. `dependencies = []`. A clone is runnable on its own.

## The three stages this provenance has been through

### Stage 1 — adapter-only (original release, `7958908`)

Veritas bound to four internal source trees at runtime through
`VERITAS_<NAME>_PATH`, and to a fifth that read a private 61-concept graph. It
redistributed none of them, so publication required no license grant — and
consequently **nobody without the internal estate could run it**, which defeats
the purpose of a public demo.

### Stage 2 — public core (migration, `e631f29`)

Those four primitives were extracted into
[`Wyrd-Flux/wyrd-evidence-core`](https://github.com/Wyrd-Flux/wyrd-evidence-core)
(Apache-2.0) and Veritas took it as an ordinary git dependency. That made Veritas
runnable by anyone — at the cost of a transitive dependency on a repository with
exactly one consumer, published only by git URL and therefore unpinned.

### Stage 3 — folded back in (this release)

The core is folded into [`veritas_demo/evidence/`](https://github.com/Wyrd-Flux/veritas/tree/main/veritas_demo/evidence)
and the dependency is removed. **The core repository was not deleted.** It is
archived and retained for provenance.

The reasoning, in the operator's words:

> The current core libraries each have exactly one public consumer. That does not
> yet justify a permanent public package boundary. A reusable-looking
> implementation is not automatically a reusable subsystem. Extraction should
> follow demonstrated reuse.

## Files in `veritas_demo/evidence/`

### Internal source, as originally recorded

| File | Internal source path | SHA-256 of source | Bytes |
|---|---|---|---|
| `predicate_semantics.py` | `C:\G1\tools\predicate_semantics.py` | `727bf9701c34236d42711c1dd7ccb33b82fe93510754417d04ef0437f89d871c` | 17,947 |
| `writeback_validator.py` | `C:\G1\tools\writeback_validator.py` | `fa33dad42cdbaafeb31783d16aea5d1e5374ab85c33077773b814241af36c1f6` | 18,498 |
| `outcome_taxonomy.py` | `C:\G1\tools\outcome_taxonomy.py` | `ff8823cfc281231e6837228a4121634b4c924d03bcfe1dadd29df4df63adf3d3` | 7,795 |
| `registry_schema.py` | `C:\Projects\state_registry\schema.py` | `6507e21e1cfd6093c9a9c4aec7c511300feb154aff298de66616b76201693f8f` | 7,095 |
| `registry.py` | `C:\Projects\state_registry\registry.py` | `a0f23135d5abb12d0a41780d68c463d00cc1b5ca3a964465c9ee08718cbec8fa` | 17,439 |

### SHA-256 as published in the core, and as folded in here

Three differ from the internal source because of mechanical extraction edits; two
are byte-identical to the source.

| File | SHA-256 as folded in here | Differs from source? |
|---|---|---|
| `predicate_semantics.py` | `727bf9701c34236d42711c1dd7ccb33b82fe93510754417d04ef0437f89d871c` | no — identical |
| `outcome_taxonomy.py` | `ff8823cfc281231e6837228a4121634b4c924d03bcfe1dadd29df4df63adf3d3` | no — identical |
| `registry_schema.py` | `6507e21e1cfd6093c9a9c4aec7c511300feb154aff298de66616b76201693f8f` | no — identical |
| `writeback_validator.py` | see note below | yes |
| `registry.py` | see note below | yes |

**Note.** `writeback_validator.py` and `registry.py` changed during this fold, for
reasons that are listed under "changes made during folding". Their hashes above
in the first table remain the authoritative record of what was extracted from
where.

### The commit the code passed through

Every file here was public at
[`Wyrd-Flux/wyrd-evidence-core@7c11c45`](https://github.com/Wyrd-Flux/wyrd-evidence-core/tree/7c11c45756e2f61df6d32cf7f961806ae410e335)
before being moved here. That repository is archived, not deleted, so that commit
and its history remain readable.

## Changes made during extraction

| Change | Why |
|---|---|
| `writeback_validator.py`: `import predicate_semantics` → `from . import predicate_semantics` | package-relative import |
| `registry.py`: `from .schema import` → `from .registry_schema import` | the module is no longer named `schema.py` |
| `registry.py`: `WORKSPACE_ROOT` gained an environment override | upstream it resolved against wherever the package was installed, which coupled evidence resolution to the operator's filesystem layout |
| `__init__.py` added | package metadata only, no logic |

## Changes made during folding

Two, both documented in place:

**`writeback_validator.py` — the script-mode import fallback was removed.**
Upstream carried

```python
try:
    from . import predicate_semantics as ps
except ImportError:  # running as a script
    import predicate_semantics as ps
```

so the file could run standalone from its own directory. Inside a package that
fallback is a liability rather than a convenience: it is a **bare absolute import
of a name that resolves to whatever else is on `sys.path`**, including a private
copy of the same module in `C:\G1\tools`. Being unimportable from the wrong place
is the safer failure. The package's own tests now enforce it — see
`test_veritas_names_no_private_estate_module`, which tokenises every shipped file
and fails on any executable private-module reference.

**`registry.py` — the workspace-root override was renamed.**
`WYRD_EVIDENCE_CORE_WORKSPACE_ROOT` became `VERITAS_WORKSPACE_ROOT`, and its
default moved up one directory level to stay correct after the package moved from
`wyrd_evidence_core/` to `veritas_demo/evidence/`. Behaviour when unset is
unchanged: relative evidence references still resolve against the repository root,
and a reference that does not resolve is still recorded as `exists: False` rather
than treated as satisfied.

## Behaviour and tests preserved

Nothing was rewritten. The three primitives ship their own self-check suites, and
they run here:

- `predicate_semantics.self_check()` — 24 predicates cross-checked
- `writeback_validator.self_check()` — 11 verdict cases
- `outcome_taxonomy.selfcheck()` — 11 self-qualification cases

All three return clean. If a single rule had changed during extraction or folding,
they would fail.

## Provenance facts

**`NO_VCS_HISTORY_AT_SOURCE`** applies to the three modules from `C:\G1\tools`.
That directory is not under version control; there is no commit history, and none
was fabricated — at extraction, at publication, or now.

**Operator attestation** (2026-09-30):

> The modules `predicate_semantics.py`, `writeback_validator.py`, and
> `outcome_taxonomy.py` were produced under my direction as part of this
> architecture. Their lack of Git/VCS history is a provenance deficiency, not
> evidence that they are third-party code.

`C:\Projects\state_registry` *is* under version control: 16 commits, all authored
by `UrukuTelal <urukutelal@users.noreply.github.com>`.

## Third-party material

None. Every file in `veritas_demo/evidence/` imports only the Python standard
library. No vendored directories, no embedded copyright headers, no upstream
third-party code. The package declares no runtime dependencies.

## Licensing

- **Veritas:** MIT. See [`LICENSE`](../LICENSE).
- **The primitives were originally published under Apache-2.0** in
  `wyrd-evidence-core`, by operator decision. They are MIT here, as part of this
  repository, which is a strictly more permissive grant of the same code by the
  same rights holder.

No license file was added to, or modified in, any internal source repository at
any stage. `C:\G1\tools` and `C:\Projects\state_registry` remain unlicensed and
unmodified.

## What is deliberately absent

| Not shipped | Why |
|---|---|
| the 61-concept G1 graph | private estate data |
| the internal `capability_inventory.py` | structurally required that graph; replaced by `capabilities.py` |
| any `C:\G1` or `C:\Projects` path | must not travel with the code |
| `state_registry/contradiction.py`, `ci_check.py`, `precommit.py` | repository-internal tooling, not the registry surface |

## If a second consumer appears

That is the condition for extracting a shared library again, and it is the
condition under which `wyrd-evidence-core` was archived rather than deleted. Until
then the primitives live here, where the only consumer can reach them without a
cross-repository install.
