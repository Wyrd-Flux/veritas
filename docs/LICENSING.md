# Licensing decision support

Recorded 2026-09-30. Read-only investigation; nothing was modified.

## The question

> May Veritas be published as an adapter-only MIT repository that binds at
> runtime to five upstream modules that have no license file?

## What the investigation found

### Ownership provenance

| # | Upstream | VCS | Author identity | Remote |
|---|---|---|---|---|
| 1 | `C:\Projects\state_registry` | **yes** — externalized gitdir, 17 commits, worktree clean | **`UrukuTelal <urukutelal@users.noreply.github.com>` — one identity across all history.** No co-authors. | `github.com/UrukuTelal/state_registry` |
| 2 | `C:\G1\tools\predicate_semantics.py` | **none** | undeterminable — NTFS owner `SAMANTHA\aobie`, no VCS | none |
| 3 | `C:\G1\tools\writeback_validator.py` | **none** | undeterminable | none |
| 4 | `C:\G1\tools\outcome_taxonomy.py` | **none** | undeterminable | none |
| 5 | `C:\G1\tools\capability_inventory.py` | **none** | undeterminable | none |

`C:\G1` is not a git repository at any level. There is no commit history, no
author, and no remote for roots 2–5. NTFS ownership (`SAMANTHA\aobie`) is the
only attribution signal, and file mtimes record when a file was last *written*,
not who wrote it.

Not one of the five carries a `Copyright`, `SPDX-License-Identifier`,
`Licensed under`, or `Author:` header.

### Are they entirely operator-owned?

**Yes, on the available evidence.**

- Root 1 has a single-author git history under the operator's own GitHub
  identity, over a 7-day window (2026-08-19 → 2026-08-26).
- Roots 2–5 have no third-party imports, no vendored subtree, and no
  copyleft dependency of any kind.
- No string literal over 150 characters exists in roots 2–5; none over 200
  characters in root 1. There is no embedded standards text, no quoted
  specification, no copied constant table.
- Grep for `per RFC/ISO/IEEE`, `adapted from`, `derived from`, `copied from`,
  `quoted from`, `vendored` returns zero real hits across all five.

### Third-party content

| Upstream | Non-stdlib imports | Vendored code |
|---|---|---|
| `state_registry` (24 modules) | **none.** Full set: `__future__, argparse, contextlib, copy, dataclasses, datetime, enum, hashlib, importlib, io, json, os, pathlib, re, shlex, shutil, subprocess, sys, tempfile, typing, unittest` — all stdlib, plus the package's own absolute self-reference | none. No `vendor/`, `third_party/`, `extern/`, `deps/` |
| `predicate_semantics` | **none.** Sole import: `from __future__ import annotations` | none |
| `writeback_validator` | **none third-party.** `__future__`, `dataclasses`, `typing` (stdlib) + `import predicate_semantics` (operator sibling, root 2) | none |
| `outcome_taxonomy` | **none.** Zero imports of any kind — pure literals and comparisons | none |
| `capability_inventory` | **none.** `json`, `os`, `re`, and a function-local `sys` inside `__main__` | none |

**No transitive license surface exists.** Nothing flows through from any third
party, so there is nothing to satisfy.

### License files anywhere else

- **Root 1: no LICENSE has ever existed.** `git log --all --diff-filter=A --
  '*LICENSE*' '*COPYING*' '*licence*'` is empty across all 17 commits. Zero of
  65 tracked files at HEAD match licen/copying/notice.
- **Roots 2–5:** no LICENSE, COPYING, or NOTICE anywhere under `C:\G1\` or any
  ancestor. `C:\G1\README.md` documents architecture, implementation map,
  research program, and roadmap — it states nothing about licensing.
- **No packaging metadata** on any root to carry a `license` field: root 1 has
  no `pyproject.toml` or `setup.py`; roots 2–5 have none of the above either.
- **Relevant contrast:** 17 sibling repos in `C:\Projects` *do* carry LICENSE
  files (`exafmm`, `Ising`, `Ising-Decoding`, `HRM`, `Substrate_Echo`,
  `Van_Nueman_AI`, `hermes-agent`, …). `state_registry` is the conspicuous
  exception — and the only one of that set with a GitHub remote.
- **Org policy exists but does not cover these roots.**
  `EchoSystems_Foundation\08_Open_Knowledge_&_IP\IP_&_Licensing\licensing_framework.md`
  sets software defaults of **MIT or Apache 2.0**, requires attribution notices
  for third-party contributions, and mandates the line "Copyright EchoSystems
  Foundation. Licensed under [license name]." Its companion
  `Software_&_Code\project_inventory.md` lists 8 licensed projects (7 MIT,
  `ugc-compiler` Apache 2.0) and states "All projects use MIT or Apache 2.0."
  **Neither `state_registry` nor `C:\G1` appears in that inventory.**
  `C:\Projects\AGENTS.md` and `MASTER_PLAN.md` contain no licensing statement.

## Does publication redistribute anything?

**No.** Veritas copies zero upstream lines. Verified mechanically:

```console
$ grep -rnE "class (Edge|Predicate|StateRegistry|ComponentState|Disposition|Verdict|OperationPolicy)\b" veritas_demo/
$ # no matches
```

Three vectors were assessed:

**(i) Runtime import.** No grant required. Import is not distribution; no copy
leaves the machine. Every module is stdlib-only plus, at most, operator-authored
siblings, so no third-party terms attach.

**(ii) Documenting existence and paths.** No grant required. Naming a path or
describing what a module does is nominative reference. Veritas documents
function ("a gate that rejects edges which invert orientation, substitute
relation type, or strengthen a claim") rather than reproducing the upstream
prose that explains it.

**(iii) Test fixtures quoting refusal codes.** No grant required, and lowest
risk. `CAUSATION_FROM_CORRELATION`, `OWNERSHIP_ESCALATION`,
`REFUSED_FALSIFYING_FIX` are short functional identifiers used as vocabulary.
Veritas asserts on the **token**, not on the paragraph of upstream rationale
around it.

**Would a future upstream LICENSE break Veritas' MIT?**

| If upstream becomes | Effect on Veritas |
|---|---|
| MIT or Apache-2.0 (the Foundation's stated defaults) | **Compatible.** MIT code may depend on either. Apache-2.0 obligations run upstream→downstream and bite only on redistribution of binaries — Veritas vendors nothing, so the residue is a NOTICE file, not an incompatibility. |
| GPL / AGPL / LGPL-with-linking / SSPL / Commons Clause / BSL | **Would break it.** Import of a GPL-family module may constitute distribution of a combined work. None of these exists on disk today. |

## Operator decision — ADAPTER-ONLY PUBLIC DEMO

**Decided 2026-09-30.** The question below was put to the operator and answered.

> **Decision:** Veritas is published as an **adapter-only public demo**.

Veritas' own adapter, CLI, tests, and documentation are MIT. Veritas binds at
runtime to operator-provided upstream copies and reproduces none of them.

### What is explicitly NOT distributed

- `state_registry`
- `predicate_semantics.py`
- `writeback_validator.py`
- `outcome_taxonomy.py`
- `capability_inventory.py`
- the G1 concept corpus
- any other internal payload

**Self-contained bundling is prohibited** until upstream licensing is
explicitly settled. That prohibition is recorded in `LICENSE` so it travels
with the repository rather than living only in this document.

### What stays explicit

- Upstream ownership and licensing remain **unresolved**.
- Veritas **grants no rights** in upstream code. A recipient acquires none by
  receiving this repository.
- Veritas has **no durable right to depend** on the upstream modules. It copies
  nothing out, which is why publication is unaffected — not a grant.
- **No license was added to any upstream project** as part of this decision,
  and none should be inferred from this repository's presence.

### What this means for a reader

You need the estate on disk to run the interesting commands. Without it, the
CLI reports what is missing and refuses to answer rather than approximating —
which is itself a demonstration of the architecture's central claim.

`find` degrades to `NO_MATCH`, which the exit-code contract treats as **data,
not failure**; see the `find` row in the README exit-code table. The upstream
inventory's own semantics are preserved rather than flattened into "absent
from the world".

### The remaining open question, unchanged

What license, if any, the upstream capabilities are offered under. It does not
block publication under the adapter-only shape. It blocks the first vendored
file, whenever that comes.

Two one-line additions would make the dependency defensible rather than merely
permitted, matching policy the operator has already written
(`EchoSystems_Foundation/08_Open_Knowledge_&_IP/IP_&_Licensing/licensing_framework.md`
sets MIT or Apache 2.0 for software):

- `C:\Projects\state_registry\LICENSE` — the more exposed of the two, since it
  has a GitHub remote and its no-license status is visible to anyone who finds
  it, whereas `C:\G1` is not published at all.
- `C:\G1\LICENSE` — so `C:\G1\tools` stops being unversioned and unlicensed at
  once.

**Not performed as part of this task**, per the operator decision. Recorded as
a recommendation only.

## For reference: the question as originally posed

An absent license is not a permissive one. Under default copyright, unlicensed
code is all-rights-reserved. Three consequences, in order of importance:

1. **Publication is unaffected.** Nothing is copied out.
2. **There is no durable right to depend on these modules.** A third party
   without the estate cannot obtain the five modules through Veritas, because
   Veritas does not carry them.
3. **The first hard stop is a single vendored file.** Veritas would then rely
   on absence of enforcement rather than on a grant.

Under the adapter-only decision, only (2) and (3) remain live.

## What could not be determined

- **Authorship of the four `C:\G1\tools` modules.** No VCS anywhere in the
  tree. NTFS owner and mtimes are the only signals, and neither identifies an
  author or a set of terms.
- **Whether `C:\G1` was ever versioned.** Absence of `.git` today does not
  distinguish "never versioned" from "versioned, then unwrapped".
- **Whether the operator considers `C:\G1` Foundation-funded.** It is absent
  from `project_inventory.md`, but nothing states that it is excluded from
  Foundation policy. Unlisted is not the same as opted out.
- **Whether `UrukuTelal/state_registry` is public.** The remote returns 404
  unauthenticated, which is equally consistent with private and nonexistent.
  This does not change any conclusion above.
- **Whether the missing license was deliberate.** The last root-1 commit is
  "Activate AUTH reconstitution repair" (2026-08-26). No commit message, issue,
  or governance record addresses licensing. Intent is indeterminate.
