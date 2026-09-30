"""PREDICATE SEMANTICS -- the registry that makes edge ORIENTATION and STRENGTH machine-checkable.

WHY THIS EXISTS
---------------
The relation vocabulary in object_concept.py had eight predicates and zero orientation
metadata. That is the specific shape of the defect this registry closes: a symmetric,
information-free predicate (RELATED_TO_CONCEPT) sat in the same flat vocabulary as a
maximally specific directional one (DEFINES_CONCEPT), and nothing in the system could
tell you that swapping them was a violation rather than a paraphrase.

The three historical failures in this corpus were NOT primarily arrow reversals. They
were authority-escalation errors:

    LOCATED_IN            used as identity evidence
    PARSES_SOURCE         strengthened into behavioural dependence
    concept OWNED_BY      propagated into path ownership

So this registry carries two independent axes, and the second is the load-bearing one:

    strength_class        how much semantic commitment does the edge assert
    may_establish_*       may this edge type EVER establish identity / ownership

An orientation checker would have caught none of the three. The may_establish_* fields
catch all three, permanently, at the predicate level rather than per-instance.

THE ASYMMETRY INVARIANT, STRUCTURALLY
------------------------------------
Moving DOWN the strength lattice is admissible loss. Moving UP is strengthening and
requires new evidence. This is encoded in requires_evidence(), not in a comment.

CAUSALITY IS NOT SPECIAL
------------------------
Causation is one member of a class of directed semantic edges, not the primitive. The
primitive is: a typed directed edge whose orientation and type are invariant unless a
transformation explicitly declares permission to alter them.
"""

from __future__ import annotations

# --- strength lattice -------------------------------------------------------------
# Pragmatic TOTAL order over semantic commitment. Cross-class moves (e.g. IDENTIFYING
# -> CAUSAL) are not merely "more"; they are reported as TYPE_SUBSTITUTION as well, so
# the simplification never silently launders a change of KIND into a change of degree.

CORRELATIONAL = 0   # co-occurrence only
STRUCTURAL = 1     # ordering, spatial, membership structure
FUNCTIONAL = 2     # dependency, derivation, parsing
IDENTIFYING = 3    # this edge names what the thing IS
CAUSAL = 4         # this edge asserts a cause-effect mechanism
AUTHORITY = 5      # this edge asserts ownership or authority over the object

STRENGTH_NAME = {
    CORRELATIONAL: "CORRELATIONAL",
    STRUCTURAL: "STRUCTURAL",
    FUNCTIONAL: "FUNCTIONAL",
    IDENTIFYING: "IDENTIFYING",
    CAUSAL: "CAUSAL",
    AUTHORITY: "AUTHORITY",
}

# --- temporal policies -----------------------------------------------------------
# Constraint on (subject_time, object_time). NONE means the predicate places no
# ordering requirement at all -- and that is a real, checkable statement, not a gap.

NO_ORDERING = "NO_ORDERING"
SUBJECT_NOT_AFTER_OBJECT = "SUBJECT_NOT_AFTER_OBJECT"      # derivative not before source
OBJECT_NOT_AFTER_SUBJECT = "OBJECT_NOT_AFTER_SUBJECT"
STRICT_SUBJECT_BEFORE_OBJECT = "STRICT_SUBJECT_BEFORE_OBJECT"   # PRECEDES
SUBJECT_NOT_BEFORE_OBJECT = "SUBJECT_NOT_BEFORE_OBJECT"      # DERIVED_FROM: derivative at/after source
OBSERVATION_ANY_TIME = "OBSERVATION_ANY_TIME"              # evidence may postdate its proposition

# --- transitivity policies --------------------------------------------------------
# FORBIDDEN       -- no transitive consequence may be asserted at all
# NON_TRANSITIVE  -- no propagation is claimed, but it is not structurally impossible
# COLLECTIVE_ONLY -- propagates within the declaring collective, nowhere else

FORBIDDEN = "FORBIDDEN"
NON_TRANSITIVE = "NON_TRANSITIVE"
COLLECTIVE_ONLY = "COLLECTIVE_ONLY"


class Predicate:
    __slots__ = ("name", "directional", "symmetric", "temporal_policy",
                 "implies_causation", "may_establish_identity",
                 "may_establish_ownership", "strength_class", "transitivity_policy",
                 "why")

    def __init__(self, name, directional, symmetric, temporal_policy, implies_causation,
                 may_establish_identity, may_establish_ownership, strength_class,
                 transitivity_policy, why):
        self.name = name
        self.directional = directional
        self.symmetric = symmetric
        self.temporal_policy = temporal_policy
        self.implies_causation = implies_causation
        self.may_establish_identity = may_establish_identity
        self.may_establish_ownership = may_establish_ownership
        self.strength_class = strength_class
        self.transitivity_policy = transitivity_policy
        self.why = why

    def as_dict(self):
        return {
            "name": self.name,
            "directional": self.directional,
            "symmetric": self.symmetric,
            "temporal_policy": self.temporal_policy,
            "implies_causation": self.implies_causation,
            "may_establish_identity": self.may_establish_identity,
            "may_establish_ownership": self.may_establish_ownership,
            "strength_class": STRENGTH_NAME[self.strength_class],
            "transitivity_policy": self.transitivity_policy,
            "why": self.why,
        }


# --- the registry ----------------------------------------------------------------
# transitivity_policy values:
#   FORBIDDEN             -- no transitive consequence may be asserted
#   NON_TRANSITIVE        -- no propagation claimed, but not explicitly forbidden
#   COLLECTIVE_ONLY       -- propagates within the declaring collective, nowhere else

PREDICATES = {}


def _p(*a, **k):
    pr = Predicate(*a, **k)
    PREDICATES[pr.name] = pr
    return pr


# --- correlational ---------------------------------------------------------------
_p("CORRELATES_WITH", False, True, NO_ORDERING, False, False, False, CORRELATIONAL,
   NON_TRANSITIVE,
   "Symmetric by construction. Orientation is NOT_APPLICABLE, so a transformation may "
   "never report an orientation violation on it. Exists so that genuine co-occurrence "
   "has somewhere to live that is not a causal claim.")

_p("MENTIONS_CONCEPT", True, False, NO_ORDERING, False, False, False, CORRELATIONAL,
   FORBIDDEN,
   "Lexical co-occurrence. A document mentioning a concept says nothing about the "
   "concept's identity or authority. This is the predicate most often over-read.")

_p("ASSOCIATED_WITH", False, True, NO_ORDERING, False, False, False, CORRELATIONAL,
   FORBIDDEN,
   "Explicitly non-causal. THE UPGRADE TRAP: ASSOCIATED_WITH -> CAUSES is the single "
   "most common semantic corruption and is always a strengthening requiring evidence.")

# --- structural ------------------------------------------------------------------
_p("PRECEDES", True, False, STRICT_SUBJECT_BEFORE_OBJECT, False, False, False, STRUCTURAL,
   NON_TRANSITIVE,
   "An ordering is not a cause. Reversal is prohibited. Answers only 'what came first'.")

_p("PRECEDES_REVISION", True, False, STRICT_SUBJECT_BEFORE_OBJECT, False, False, False,
   STRUCTURAL, FORBIDDEN,
   "One revision of an artifact precedes another. Explicitly carries no identity claim: "
   "knowing which revision is current tells you nothing about what the corpus IS.")

_p("LOCATED_IN", True, False, NO_ORDERING, False, False, False, STRUCTURAL, FORBIDDEN,
   "Spatial/containment only. MAY NOT ESTABLISH IDENTITY, ever. This predicate is the "
   "canonical historical failure: a receipt stored under a folder was reconstructed as "
   "'the receipt establishes the concept'.")

_p("MEMBER_OF_CONCEPT_CORPUS", True, False, NO_ORDERING, False, False, False, STRUCTURAL,
   "COLLECTIVE_ONLY",
   "Collective membership. Does not make the member a subject-of, a definer of, or "
   "individually authoritative, and confers no folder authority. Propagates only within "
   "the declaring collective.")

# --- functional ------------------------------------------------------------------
_p("DERIVED_FROM", True, False, SUBJECT_NOT_BEFORE_OBJECT, False, False, False, FUNCTIONAL,
   FORBIDDEN,
   "Derivative cannot predate its source. IMPLIES NO CAUSATION: DERIVED_FROM is not "
   "CAUSES reversed, even though prose routinely describes it that way.")

_p("REQUIRES", True, False, NO_ORDERING, False, False, False, FUNCTIONAL, FORBIDDEN,
   "Dependency without causation. A GPU runtime does not conceptually cause the "
   "computation; it is required by it.")

_p("ENABLES", True, False, NO_ORDERING, False, False, False, FUNCTIONAL, FORBIDDEN,
   "Permission or precondition, not production of the effect.")

_p("PUBLICATION_DERIVATIVE_OF", True, False, SUBJECT_NOT_BEFORE_OBJECT, False, False, False,
   FUNCTIONAL, FORBIDDEN,
   "A publication artifact is a derivative of a source snapshot. Directional: the "
   "publication is at or after what it derives from. Establishes neither identity nor "
   "ownership, and confers no authority in either direction. Registering this explicitly "
   "matters: it had been used in G1-CORPUS-MOSHI-PUBLICATION before it existed here, and "
   "the writeback validator refused it for exactly that reason.")

_p("PARSES_SOURCE", True, False, NO_ORDERING, False, False, False, FUNCTIONAL, FORBIDDEN,
   "A consumer reading a canon. MAY NOT ESTABLISH IDENTITY OR BEHAVIOURAL DEPENDENCE. "
   "The measured Topobionts relation was DERIVED_TRANSCRIPTION, and "
   "LIVE_BEHAVIORAL_CONSUMER was refused on exactly this predicate.")

_p("VALIDATION_ORACLE_AGAINST_SOURCE", True, False, OBSERVATION_ANY_TIME, False, False,
   False, FUNCTIONAL, FORBIDDEN,
   "A test grades against a source. Observation may postdate the proposition. Does not "
   "make the source authoritative over the system under test.")

_p("IMPLEMENTS_CONCEPT", True, False, NO_ORDERING, False, False, False, FUNCTIONAL,
   FORBIDDEN,
   "Realisation, not identity and not ownership.")

# --- identifying -----------------------------------------------------------------
_p("SUBJECT_OF_DOCUMENT", True, False, NO_ORDERING, False, True, False, IDENTIFYING,
   FORBIDDEN,
   "One of only two predicates permitted to establish that a document is ABOUT a thing.")

_p("DEFINES_CONCEPT", True, False, NO_ORDERING, False, True, False, IDENTIFYING,
   FORBIDDEN,
   "One of only two predicates permitted to establish what a concept is. Note that "
   "establishing IDENTITY is not establishing AUTHORITY -- those are separate axes.")

# --- causal ----------------------------------------------------------------------
_p("REVALIDATED_BY", True, False, SUBJECT_NOT_BEFORE_OBJECT, False, False, False, FUNCTIONAL,
   FORBIDDEN,
   "A recorded defect was revalidated by a specific receipt. Directional and dated: the "
   "revalidation cannot precede the record it examines. It asserts ONLY that a bounded check "
   "was run against that record and produced a current state. It does not assert that the "
   "defect was FIXED -- a revalidation can confirm a defect is still present, and that "
   "confirmation is itself the finding. It establishes no identity, no ownership, and no "
   "causation.")

_p("RESOLVED_BY", True, False, SUBJECT_NOT_AFTER_OBJECT, False, False, False, FUNCTIONAL,
   FORBIDDEN,
   "A recorded defect was resolved by a specific confirmation receipt. Directional and "
   "dated: a resolution cannot precede the defect it resolves. It asserts ONLY that a "
   "bounded confirmation, evaluated against a positive predicate, produced the state "
   "RESOLVED. It does not assert that a repair was MECHANICAL, that any person fixed "
   "anything, or that the defect could never recur -- a resolution is a statement about "
   "evidence at a time, not a permanent property of the defect.")

_p("CAUSES", True, False, SUBJECT_NOT_AFTER_OBJECT, True, False, False, CAUSAL, FORBIDDEN,
   "Genuine cause-effect. Cause not after effect. Still may NOT establish identity: a "
   "cause explains an effect without naming what the effect IS.")

_p("RESOLVES", True, False, NO_ORDERING, True, False, False, CAUSAL, FORBIDDEN,
   "A change resolves a defect. Motivation is not causation and is tracked separately.")

_p("MOTIVATES", True, False, NO_ORDERING, True, False, False, CAUSAL, FORBIDDEN,
   "A defect can motivate a redesign without technically causing the implementation. "
   "Recorded separately precisely because prose collapses the two.")

# --- authority -------------------------------------------------------------------
_p("OWNED_BY_OPERATOR", True, False, NO_ORDERING, False, False, True, AUTHORITY,
   FORBIDDEN,
   "Operator ownership of a CONCEPT. TRANSITIVITY FORBIDDEN: this does NOT propagate to "
   "the paths associated with the concept. That propagation is the third historical "
   "failure, and it is now unrepresentable rather than merely discouraged.")

_p("OWNED_BY_CONCEPT", True, False, NO_ORDERING, False, False, True, AUTHORITY, FORBIDDEN,
   "A concept owns a path. Establishes ownership but NOT identity, and may only be "
   "asserted against a path the operator has actually bound.")

_p("BRIDGELOGGER_REGISTERS_ROW", True, False, NO_ORDERING, False, False, False, STRUCTURAL,
   FORBIDDEN,
   "A ledger registers a row. The BridgeLedger schema carries no corpus-membership "
   "field, so this predicate can never be read as membership evidence.")


# --- API -------------------------------------------------------------------------
def get(name):
    """Fetch a predicate. Unknown predicates RAISE -- the registry fails closed.

    An unregistered predicate is not a neutral unknown; it is an untyped edge, and
    untyped edges are exactly how a universal RELATES_TO primitive creeps back in.
    """
    if name not in PREDICATES:
        raise KeyError("UNREGISTERED_PREDICATE: %r is not in the predicate registry; "
                       "refusing to treat an untyped edge as evidence" % name)
    return PREDICATES[name]


def known(name):
    return name in PREDICATES


def requires_evidence(before_strength, after_strength):
    """THE ASYMMETRY INVARIANT, STRUCTURALLY ENCODED.

    Down is admissible loss. Up is strengthening and needs evidence. Equal is free.
    This is the whole rule; there is no commentary version of it elsewhere.
    """
    return after_strength > before_strength


def weakening_admissible(before_strength, after_strength):
    return after_strength < before_strength


def strength_of(name):
    return get(name).strength_class


def self_check():
    """Registry self-qualification. Fails loudly on a structurally incoherent registry."""
    problems = []
    for p in PREDICATES.values():
        if p.symmetric and p.directional:
            problems.append("%s: symmetric predicates must not be directional" % p.name)
        if p.symmetric and p.may_establish_identity:
            problems.append("%s: a symmetric predicate must not establish identity" % p.name)
        if p.symmetric and p.may_establish_ownership:
            problems.append("%s: a symmetric predicate must not establish ownership" % p.name)
        if p.implies_causation and p.strength_class < CAUSAL:
            problems.append("%s: implies_causation below CAUSAL strength" % p.name)
        if p.may_establish_identity and p.strength_class < IDENTIFYING:
            problems.append("%s: may_establish_identity below IDENTIFYING strength" % p.name)
        if p.may_establish_ownership and p.strength_class < AUTHORITY:
            problems.append("%s: may_establish_ownership below AUTHORITY strength" % p.name)
        if p.transitivity_policy == "FORBIDDEN" and p.may_establish_ownership \
                and p.name.startswith("OWNED_BY_OPERATOR"):
            pass  # intentional: operator ownership must never propagate
        if not p.why or len(p.why) < 40:
            problems.append("%s: predicate without a recorded reason" % p.name)
    ident = sorted(n for n, p in PREDICATES.items() if p.may_establish_identity)
    own = sorted(n for n, p in PREDICATES.items() if p.may_establish_ownership)
    if ident != ["DEFINES_CONCEPT", "SUBJECT_OF_DOCUMENT"]:
        problems.append("identity-establishing set drifted: %s" % ident)
    if own != ["OWNED_BY_CONCEPT", "OWNED_BY_OPERATOR"]:
        problems.append("ownership-establishing set drifted: %s" % own)
    return problems


if __name__ == "__main__":
    probs = self_check()
    print("PREDICATE SEMANTICS REGISTRY")
    print("  predicates: %d" % len(PREDICATES))
    by = {}
    for p in PREDICATES.values():
        by.setdefault(STRENGTH_NAME[p.strength_class], []).append(p.name)
    for k in ("CORRELATIONAL", "STRUCTURAL", "FUNCTIONAL", "IDENTIFYING", "CAUSAL", "AUTHORITY"):
        if k in by:
            print("  %-14s %d  %s" % (k, len(by[k]), ", ".join(sorted(by[k]))))
    print()
    print("  may_establish_identity : %s" % sorted(n for n, p in PREDICATES.items()
                                                  if p.may_establish_identity))
    print("  may_establish_ownership: %s" % sorted(n for n, p in PREDICATES.items()
                                                  if p.may_establish_ownership))
    print("  implies_causation      : %s" % sorted(n for n, p in PREDICATES.items()
                                                  if p.implies_causation))
    print("  symmetric (no orientation) : %s" % sorted(n for n, p in PREDICATES.items()
                                                       if p.symmetric))
    print()
    print("self_check problems: %d" % len(probs))
    for x in probs:
        print("  %s" % x)
    raise SystemExit(1 if probs else 0)
