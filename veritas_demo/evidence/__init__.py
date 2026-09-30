"""Evidence primitives: the governed behaviour Veritas exists to exercise.

These five modules are the implementation Veritas reports on. They are not a
framework and not a wrapper -- they are the lattice, the validator, the taxonomy
and the registry themselves, folded in so this repository is self-contained.

| Module | Question |
|---|---|
| ``predicate_semantics`` | what does this evidence permit me to claim? |
| ``writeback_validator`` | may I write this relation set back over existing state? |
| ``outcome_taxonomy`` | how should this attempt be classified, given how it ended? |
| ``registry`` / ``registry_schema`` | what is a component's state, and can its history be verified? |

Provenance for every file is in ``docs/PROVENANCE.md``: the internal source path,
the source SHA-256, and the fact that three of them had no version control
history at source.
"""
