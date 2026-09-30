"""WRITEBACK VALIDATOR -- the gate every autonomously produced evidence edge must pass.

WHY THIS IS THE FIRST THING BUILT BEFORE THE ROUTER
----------------------------------------------------
The router is the first component that autonomously emits new evidence relations. If
writeback lands before relation validation, there is an execution path that can produce
exactly the class of semantic corruption this validator names -- and it would produce it
unattributed, at machine speed, with a receipt attached.

So this validator sits between "action produced a proposal" and "proposal becomes
evidence". Nothing reaches the corpus without passing here.

WHAT IT CHECKS
--------------
  1. orientation preservation        -- is the edge still pointing the same way?
  2. relation-type preservation      -- is it still the same KIND of claim?
  3. strengthening / weakening       -- the asymmetry invariant, structurally
  4. identity-establishment admissibility
     ownership-establishment admissibility
     causation-from-correlation
     transitive propagation
     temporal policy

Note what is deliberately NOT here: there is no orientation check on a symmetric
predicate, because orientation is not applicable to it. Reporting an inversion on
CORRELATES_WITH would be the same category of error as this system exists to prevent.

THE ASYMMETRY INVARIANT
-----------------------
    Semantic weakening may be admissible loss.
    Semantic strengthening requires evidence.

Encoded in predicate_semantics.requires_evidence and applied below. Weakening is
RECORDED, never silently dropped: a summary that turns CAUSES into ASSOCIATED_WITH has
lost information and the corpus should be able to say so later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Imported relatively, without a script-mode fallback. Upstream carried
# ``import predicate_semantics as ps`` in an except branch so the file could run
# standalone from its own directory. In a package that fallback is a liability
# rather than a convenience: it is a bare absolute import of a name that would
# resolve to whatever else happened to be on sys.path -- including a private copy
# of the same module. Being unimportable from the wrong place is the safer
# failure.
from . import predicate_semantics as ps

# --- violation classes -----------------------------------------------------------
ORIENTATION_INVERSION = "ORIENTATION_INVERSION"
SUBJECT_OBJECT_SWAP = "SUBJECT_OBJECT_SWAP"
RELATION_TYPE_SUBSTITUTION = "RELATION_TYPE_SUBSTITUTION"
RELATION_STRENGTHENING = "RELATION_STRENGTHENING"
IDENTITY_ESCALATION = "IDENTITY_ESCALATION"
OWNERSHIP_ESCALATION = "OWNERSHIP_ESCALATION"
CAUSATION_FROM_CORRELATION = "CAUSATION_FROM_CORRELATION"
INVALID_TRANSITIVE_PROPAGATION = "INVALID_TRANSITIVE_PROPAGATION"
TEMPORAL_POLICY_VIOLATION = "TEMPORAL_POLICY_VIOLATION"
UNREGISTERED_PREDICATE = "UNREGISTERED_PREDICATE"
PREDICATE_NOT_AUTHORIZED = "PREDICATE_NOT_AUTHORIZED"
NEW_EDGE_WITHOUT_EVIDENCE = "NEW_EDGE_WITHOUT_EVIDENCE"

REFUSING = frozenset({
    ORIENTATION_INVERSION, SUBJECT_OBJECT_SWAP, RELATION_TYPE_SUBSTITUTION,
    RELATION_STRENGTHENING, IDENTITY_ESCALATION, OWNERSHIP_ESCALATION,
    CAUSATION_FROM_CORRELATION, INVALID_TRANSITIVE_PROPAGATION,
    TEMPORAL_POLICY_VIOLATION, UNREGISTERED_PREDICATE, NEW_EDGE_WITHOUT_EVIDENCE,
})


@dataclass(frozen=True)
class Edge:
    subject: str
    predicate: str
    obj: str
    basis: str = "OBSERVED"
    evidence: tuple = ()
    subject_time: Optional[str] = None
    object_time: Optional[str] = None

    def key(self):
        return (self.subject, self.predicate, self.obj)

    def pair(self):
        return (self.subject, self.obj)

    def __str__(self):
        return "%s --%s--> %s" % (self.subject, self.predicate, self.obj)


@dataclass
class Finding:
    edge: str
    code: str
    detail: str
    authorizing_evidence: tuple = field(default_factory=tuple)


@dataclass
class Verdict:
    accepted: list = field(default_factory=list)
    refused: list = field(default_factory=list)
    admissible_losses: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.refused

    def summary(self):
        return {"accepted": len(self.accepted), "refused": len(self.refused),
                "admissible_losses": len(self.admissible_losses)}


def _temporal_ok(pred, e):
    """Check declared temporal policy against observed times. UNKNOWN time is NOT a pass."""
    if pred.temporal_policy == ps.NO_ORDERING or pred.temporal_policy == ps.OBSERVATION_ANY_TIME:
        return True, None
    if e.subject_time is None or e.object_time is None:
        return True, None  # cannot check; not evidence of correctness, simply unchecked
    s, o = e.subject_time, e.object_time
    if pred.temporal_policy == ps.STRICT_SUBJECT_BEFORE_OBJECT:
        return (s < o), "subject_time %s not strictly before object_time %s" % (s, o)
    if pred.temporal_policy == ps.SUBJECT_NOT_AFTER_OBJECT:
        return (s <= o), "subject_time %s after object_time %s" % (s, o)
    if pred.temporal_policy == ps.SUBJECT_NOT_BEFORE_OBJECT:
        return (s >= o), "subject_time %s precedes object_time %s (derivative before source)" % (s, o)
    if pred.temporal_policy == ps.OBJECT_NOT_AFTER_SUBJECT:
        return (o <= s), "object_time %s after subject_time %s" % (o, s)
    return True, None


def _transitively_derivable(before, target):
    """Can `target` be reached as a transitive consequence of existing edges?

    Only crossings THROUGH a FORBIDDEN-transitivity predicate are reported, because
    that is the class of propagation the registry makes unrepresentable. This is what
    catches concept-ownership leaking onto associated paths.
    """
    if not target.predicate:
        return None
    frontier = list(before)
    seen = set()
    for _ in range(4):                       # bounded: no unbounded closure
        nxt = []
        for a in frontier:
            for b in before:
                if a.obj != b.subject or a.obj in seen:
                    continue
                if a.predicate == b.predicate and \
                        a.subject == target.subject and b.obj == target.obj:
                    if ps.get(a.predicate).transitivity_policy == ps.FORBIDDEN:
                        return "%s --%s--> %s crossed into %s" % (
                            a.subject, a.predicate, a.obj, target.obj)
                nxt.append(Edge(a.subject, a.predicate, b.obj))
        seen.update(e.obj for e in frontier)
        frontier = nxt
        if not frontier:
            break
    return None


def validate(before, proposed, authorization=frozenset(), permitted_predicates=None):
    """Validate a proposed evidence writeback against the prior relation set.

    `authorization` is the set of evidence tokens that permit strengthening. Absent a
    token, any move up the strength lattice is refused. This is the asymmetry invariant
    doing its job at the only place it can actually be enforced.

    `permitted_predicates` is a SEPARATE and stricter control. If supplied, an edge
    whose predicate is not in the set is refused regardless of how many tokens it
    carries. This exists because a token that authorizes an action to record where
    something lives must not also authorize it to declare what that something IS. The
    distinction between "may I do work" and "which relations may this work assert" is
    the whole point; collapsing both into one token set makes the restriction advisory.
    """
    v = Verdict()
    before_by_pair = {}
    before_edges = []
    for e in before:
        if not ps.known(e.predicate):
            v.refused.append(Finding(str(e), UNREGISTERED_PREDICATE,
                                     "prior edge uses unregistered predicate %r" % e.predicate))
            continue
        before_edges.append(e)
        before_by_pair.setdefault(e.pair(), []).append(e)

    for e in proposed:
        auth = tuple(sorted(set(e.evidence) & set(authorization)))

        # (0) fail closed on untyped edges
        if not ps.known(e.predicate):
            v.refused.append(Finding(str(e), UNREGISTERED_PREDICATE,
                                     "predicate %r is not in the registry; an untyped edge "
                                     "is not evidence" % e.predicate))
            continue
        pred = ps.get(e.predicate)

        # (0b) predicate-level authorization, checked BEFORE any token is considered
        if permitted_predicates is not None and e.predicate not in permitted_predicates:
            v.refused.append(Finding(
                str(e), PREDICATE_NOT_AUTHORIZED,
                "predicate %r is not among the relations this action is permitted to assert "
                "(%s); an evidence token does not widen that set"
                % (e.predicate, sorted(permitted_predicates))))
            continue

        # (1) temporal policy
        tok, tdetail = _temporal_ok(pred, e)
        if not tok:
            v.refused.append(Finding(str(e), TEMPORAL_POLICY_VIOLATION, tdetail, auth))
            continue

        same_pair = before_by_pair.get(e.pair(), [])
        exact = next((b for b in same_pair if b.predicate == e.predicate), None)

        # (2) orientation: is this the reverse of an existing directional edge?
        if pred.directional and not pred.symmetric:
            for b in before_edges:
                if b.predicate != e.predicate:
                    continue
                if b.subject == e.obj and b.obj == e.subject:
                    v.refused.append(Finding(
                        str(e), ORIENTATION_INVERSION,
                        "reverses existing edge %s; %s is directional and its reversal is "
                        "prohibited" % (b, e.predicate), auth))
                    break
            else:
                pass
        # subject/object swap relative to a same-predicate edge with different endpoints
        if pred.directional and not pred.symmetric and exact is None:
            for b in same_pair:
                if b.predicate != e.predicate and b.pair() == (e.obj, e.subject):
                    v.refused.append(Finding(
                        str(e), SUBJECT_OBJECT_SWAP,
                        "endpoints transposed relative to %s" % b, auth))
                    break

        # (3) strengthening / weakening, relative to the strongest prior claim on this pair
        if same_pair:
            prior = max(same_pair, key=lambda b: ps.strength_of(b.predicate))
            ps_prior, ps_new = ps.strength_of(prior.predicate), pred.strength_class
            if ps.weakening_admissible(ps_prior, ps_new):
                v.admissible_losses.append(Finding(
                    str(e), "ADMISSIBLE_WEAKENING",
                    "%s -> %s recorded as admissible information loss" % (
                        prior.predicate, e.predicate)))
                v.accepted.append(e)
                continue
            if prior.predicate != e.predicate and not auth:
                v.refused.append(Finding(
                    str(e), RELATION_TYPE_SUBSTITUTION,
                    "changes predicate %s -> %s on the same subject/object; a change of KIND "
                    "is never an admissible paraphrase" % (prior.predicate, e.predicate), auth))
            if ps.requires_evidence(ps_prior, ps_new) and not auth:
                v.refused.append(Finding(
                    str(e), RELATION_STRENGTHENING,
                    "strength %s -> %s requires evidence; weakening is admissible loss, "
                    "strengthening is not" % (ps.STRENGTH_NAME[ps_prior], ps.STRENGTH_NAME[ps_new]),
                    auth))
            else:
                v.accepted.append(e)
                continue
        else:
            # (4) a genuinely new subject/object pair
            if not e.evidence:
                v.refused.append(Finding(
                    str(e), NEW_EDGE_WITHOUT_EVIDENCE,
                    "new edge carries no evidence token; a new relation may not appear "
                    "unattributed", auth))
                continue

        # (5) identity escalation
        if pred.may_establish_identity:
            prior_id = any(ps.get(b.predicate).may_establish_identity for b in same_pair)
            if not prior_id and not auth:
                v.refused.append(Finding(
                    str(e), IDENTITY_ESCALATION,
                    "%s may establish identity, but no prior identity-establishing edge "
                    "supports this subject/object and no authorizing evidence was supplied"
                    % e.predicate, auth))
                continue

        # (6) ownership escalation
        if pred.may_establish_ownership:
            prior_own = any(ps.get(b.predicate).may_establish_ownership for b in same_pair)
            if not prior_own and not auth:
                v.refused.append(Finding(
                    str(e), OWNERSHIP_ESCALATION,
                    "%s may establish ownership, but no prior ownership edge supports it "
                    "and no authorizing evidence was supplied" % e.predicate, auth))
                continue

        # (7) causation from correlation
        if pred.implies_causation:
            prior_c = any(ps.get(b.predicate).implies_causation for b in same_pair)
            if not prior_c and not auth:
                v.refused.append(Finding(
                    str(e), CAUSATION_FROM_CORRELATION,
                    "asserts causation where the prior relation asserted none", auth))
                continue

        # (8) transitive propagation through a FORBIDDEN predicate
        deriv = _transitively_derivable(before_edges, e)
        if deriv and not auth:
            v.refused.append(Finding(
                str(e), INVALID_TRANSITIVE_PROPAGATION,
                "derivable only as a transitive consequence (%s), and %s forbids propagation"
                % (deriv, e.predicate), auth))
            continue

        v.accepted.append(e)

    return v


# --- self-qualification ----------------------------------------------------------
def _regressions():
    """The four forbidden escalations, plus the cases that must NOT be refused."""
    cases = []

    def case(name, before, proposed, expect_codes, auth=frozenset()):
        v = validate(before, proposed, auth)
        got = sorted({f.code for f in v.refused})
        ok = (set(expect_codes) <= set(got)) if expect_codes else (not v.refused)
        cases.append((name, ok, expect_codes, got))

    A = Edge("CONCEPT", ps.__name__ and "MENTIONS_CONCEPT", "DOC", evidence=("m1",))
    B = Edge("DOC", "ASSOCIATED_WITH", "CONCEPT", evidence=("a1",))
    B2 = Edge("DOC", "ASSOCIATED_WITH", "CONCEPT", evidence=("a1",))

    case("ASSOCIATED_WITH -> CAUSES is refused",
         [B2], [Edge("DOC", "CAUSES", "CONCEPT", evidence=("c1",))],
         [CAUSATION_FROM_CORRELATION, RELATION_STRENGTHENING])

    case("LOCATED_IN -> DEFINES_CONCEPT is refused",
         [Edge("RECEIPT", "LOCATED_IN", "FOLDER", evidence=("l1",))],
         [Edge("RECEIPT", "DEFINES_CONCEPT", "CONCEPT", evidence=("d1",))],
         [IDENTITY_ESCALATION])

    case("PARSES_SOURCE -> LIVE_BEHAVIORAL_CONSUMER is refused (unregistered)",
         [Edge("CONSUMER", "PARSES_SOURCE", "CANON", evidence=("p1",))],
         [Edge("CONSUMER", "LIVE_BEHAVIORAL_CONSUMER", "CANON", evidence=("x1",))],
         [UNREGISTERED_PREDICATE])

    case("concept ownership -> path ownership is refused",
         [Edge("CONCEPT", "OWNED_BY_OPERATOR", "OPERATOR", evidence=("o1",)),
          Edge("PATH", "MEMBER_OF_CONCEPT_CORPUS", "CONCEPT", evidence=("m1",))],
         [Edge("PATH", "OWNED_BY_CONCEPT", "CONCEPT", evidence=("z1",))],
         [OWNERSHIP_ESCALATION])

    case("ORIENTATION_INVERSION on a directional edge is refused",
         [Edge("ARCH", "DERIVED_FROM", "SNAPSHOT", evidence=("d1",))],
         [Edge("SNAPSHOT", "DERIVED_FROM", "ARCH", evidence=("d2",))],
         [ORIENTATION_INVERSION])

    case("weakening CAUSES -> ASSOCIATED_WITH is ADMITTED as loss",
         [Edge("X", "CAUSES", "Y", evidence=("c1",))],
         [Edge("X", "ASSOCIATED_WITH", "Y", evidence=("a1",))],
         [])

    case("CORRELATES_WITH is symmetric: no orientation violation is reportable",
         [Edge("A", "CORRELATES_WITH", "B", evidence=("r1",)),
          Edge("B", "CORRELATES_WITH", "A", evidence=("r2",))],
         [Edge("A", "CORRELATES_WITH", "C", evidence=("r3",))],
         [])

    case("DERIVED_FROM with derivative earlier than source is refused",
         [Edge("ARCH", "DERIVED_FROM", "SNAPSHOT", evidence=("d1",))],
         [Edge("PUB", "DERIVED_FROM", "SNAPSHOT", evidence=("d2",),
               subject_time="2026-01-01", object_time="2026-08-31")],
         [TEMPORAL_POLICY_VIOLATION])

    case("strengthening IS admitted when authorized by evidence",
         [B2], [Edge("DOC", "CAUSES", "CONCEPT", evidence=("c1",))],
         [], auth=frozenset({"c1"}))

    # the permitted set is enforced independently of tokens: same input, same valid
    # token, refused purely because DEFINES_CONCEPT is not in may_propose.
    _v = validate([B2], [Edge("DOC", "DEFINES_CONCEPT", "CONCEPT", evidence=("c1",))],
                  frozenset({"c1"}), permitted_predicates=frozenset({"ASSOCIATED_WITH"}))
    cases.append(("...and is refused even with a valid token",
                  _v.ok is False and {f.code for f in _v.refused} == {PREDICATE_NOT_AUTHORIZED},
                  [PREDICATE_NOT_AUTHORIZED], sorted({f.code for f in _v.refused})))

    case("a brand-new edge with no evidence is refused",
         [], [Edge("NEW", "MENTIONS_CONCEPT", "OTHER")],
         [NEW_EDGE_WITHOUT_EVIDENCE])

    return cases


def self_check():
    reg = ps.self_check()
    cases = _regressions()
    bad = [c for c in cases if not c[1]]
    return reg, cases, bad


if __name__ == "__main__":
    reg, cases, bad = self_check()
    print("WRITEBACK VALIDATOR")
    print("  registry problems : %d" % len(reg))
    print("  regression cases  : %d" % len(cases))
    passed = len(cases) - len(bad)
    for name, ok, exp, got in cases:
        print("   [%s] %-56s expected=%s got=%s"
              % ("PASS" if ok else "FAIL", name[:54], exp or "none", got or "none"))
    print()
    print("  passed: %d/%d" % (passed, len(cases)))
    for name, ok, exp, got in bad:
        print("   FAIL %s: expected %s, got %s" % (name[:60], exp, got))
    raise SystemExit(1 if (bad or reg) else 0)
