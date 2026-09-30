"""OUTCOME TAXONOMY -- the classification vocabulary for defect lifecycles.

A lifecycle runner that collapses every outcome into a fixed/not-fixed bit cannot tell a
repair from a refusal, and a refusal from a defect that stopped applying. Those are three
different facts about the world and they have different consequences, so they get different
classes.

Four families, deliberately kept apart:

  RESOLVED  the defect was addressed -- by editing, by deciding, or by evidence superseding it
  REFUSED   a repair was available and was declined, for a stated reason
  CLOSED    the subject ceased to be the thing in force; nothing was repaired
  OPEN      nobody could close it, and the reason is recorded

CLOSED is the one most systems omit. Without it, "the manifest was superseded" and "the
manifest was fixed" are the same cell, and a portfolio that counts them together slowly turns
archaeology into productivity. A closure asserts that no repair occurred.
"""

RESOLVED_BY_MUTATION = "RESOLVED_BY_MUTATION"
RESOLVED_BY_DECISION = "RESOLVED_BY_DECISION"
RESOLVED_BY_REVALIDATION = "RESOLVED_BY_REVALIDATION"

# NOT a resolution. The defect did not get better; the thing it was about ceased to be the
# thing in force. Reporting this as RESOLVED would assert a repair that never happened. It is
# a CLOSURE, and closures are tracked apart from resolutions because a portfolio that counts
# them together overstates how much was actually fixed.
CLOSED_SUBJECT_SUPERSEDED = "CLOSED_SUBJECT_SUPERSEDED"

REFUSED_FALSIFYING_FIX = "REFUSED_FALSIFYING_FIX"
REFUSED_SEMANTICALLY_UNJUSTIFIED = "REFUSED_SEMANTICALLY_UNJUSTIFIED"
REFUSED_SCOPE_EXCEEDED = "REFUSED_SCOPE_EXCEEDED"

UNRESOLVED_EVIDENCE_INSUFFICIENT = "UNRESOLVED_EVIDENCE_INSUFFICIENT"
BLOCKED_CAPABILITY_MISSING = "BLOCKED_CAPABILITY_MISSING"
NOT_ACTIONABLE = "NOT_ACTIONABLE"

DESCRIPTIONS = {
    RESOLVED_BY_MUTATION: "a file was edited and the edit was verified",
    RESOLVED_BY_DECISION: "a choice was recorded where more than one repair was admissible",
    RESOLVED_BY_REVALIDATION: "current evidence superseded a stale claim, no edit",
    CLOSED_SUBJECT_SUPERSEDED: "the subject ceased to be in force; no repair occurred",
    REFUSED_FALSIFYING_FIX: "the available repair would falsify the claim being checked",
    REFUSED_SEMANTICALLY_UNJUSTIFIED: "no instrument can recover the governing meaning",
    REFUSED_SCOPE_EXCEEDED: "a valid repair reaches beyond the declared scope",
    UNRESOLVED_EVIDENCE_INSUFFICIENT: "evidence is too thin to decide, and cannot be made more",
    BLOCKED_CAPABILITY_MISSING: "the work needs a capability this system does not have",
    NOT_ACTIONABLE: "the claim is deliberately not a thing to act on",
}

RESOLVED_CLASSES = frozenset({RESOLVED_BY_MUTATION, RESOLVED_BY_DECISION,
                              RESOLVED_BY_REVALIDATION})
REFUSED_CLASSES = frozenset({REFUSED_FALSIFYING_FIX, REFUSED_SEMANTICALLY_UNJUSTIFIED,
                             REFUSED_SCOPE_EXCEEDED})
CLOSED_CLASSES = frozenset({CLOSED_SUBJECT_SUPERSEDED})
OPEN_CLASSES = frozenset({UNRESOLVED_EVIDENCE_INSUFFICIENT, BLOCKED_CAPABILITY_MISSING,
                          NOT_ACTIONABLE})

ALL_CLASSES = RESOLVED_CLASSES | REFUSED_CLASSES | OPEN_CLASSES | CLOSED_CLASSES

# A bare "RESOLVED" is exactly the collapse this taxonomy exists to prevent, so it is a
# distinct token rather than an alias for a family.
RESOLVED = "RESOLVED"
UNCLASSIFIED = "UNCLASSIFIED"


def family(cls):
    if cls in RESOLVED_CLASSES:
        return "RESOLVED"
    if cls in REFUSED_CLASSES:
        return "REFUSED"
    if cls in CLOSED_CLASSES:
        return "CLOSED"
    if cls in OPEN_CLASSES:
        return "OPEN"
    return "UNCLASSIFIED"


def summarise(counts):
    counts = counts or {}
    resolved = sum(counts.get(c, 0) for c in RESOLVED_CLASSES)
    refused = sum(counts.get(c, 0) for c in REFUSED_CLASSES)
    closed = sum(counts.get(c, 0) for c in CLOSED_CLASSES)
    opened = sum(counts.get(c, 0) for c in OPEN_CLASSES)
    return {"resolved": resolved, "refused": refused, "closed": closed, "open": opened,
            "counts": counts, "total": resolved + refused + closed + opened}


def _counts_from(s):
    """Accept a summary dict, a counts dict, or a list of records with an 'outcome'."""
    if isinstance(s, dict) and "counts" in s:
        return s
    if isinstance(s, dict):
        return summarise(s)
    counts = {}
    for r in (s or []):
        o = r.get("outcome") if isinstance(r, dict) else r
        if o in ALL_CLASSES:
            counts[o] = counts.get(o, 0) + 1
        elif o:
            counts[UNCLASSIFIED] = counts.get(UNCLASSIFIED, 0) + 1
    return summarise(counts)


def render(s):
    s = _counts_from(s)
    counts = s["counts"]
    out = ["=" * 78, "COVERAGE METRIC (taxonomy)", "=" * 78]
    out.append("  eligible_defects            : %d" % s["total"])
    out.append("  RESOLVED                    : %d" % s["resolved"])
    for c in sorted(RESOLVED_CLASSES):
        if counts.get(c):
            out.append("     %-34s %d" % (c, counts[c]))
    out.append("  CORRECTLY_REFUSED           : %d" % s["refused"])
    for c in sorted(REFUSED_CLASSES):
        if counts.get(c):
            out.append("     %-34s %d" % (c, counts[c]))
    out.append("  CLOSED (superseded, NOT fixed) : %d" % s["closed"])
    for c in sorted(CLOSED_CLASSES):
        if counts.get(c):
            out.append("     %-34s %d" % (c, counts[c]))
    out.append("  OPEN                        : %d" % s["open"])
    for c in sorted(OPEN_CLASSES):
        if counts.get(c):
            out.append("     %-34s %d" % (c, counts[c]))
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------
# A MODULE WITH NO __main__ IS NOT A GATE. It exits 0 forever, prints nothing, and a gate that
# cannot fail is worse than no gate because it gets counted as coverage. The discovery audit
# found this by looking for a non-zero exit path instead of by reading the gate's output.
# ---------------------------------------------------------------------------------------------
def selfcheck():
    errs = []
    if len(ALL_CLASSES) != (len(RESOLVED_CLASSES) + len(REFUSED_CLASSES)
                            + len(OPEN_CLASSES) + len(CLOSED_CLASSES)):
        errs.append("class families overlap or do not cover the union")
    if RESOLVED_CLASSES & CLOSED_CLASSES:
        errs.append("a closure is also a resolution -- the conflation this exists to prevent")
    for c in ALL_CLASSES:
        if c != c.strip() or c != c.upper():
            errs.append("class %r is not a stable token" % c)
        if c not in DESCRIPTIONS:
            errs.append("class %s has no description" % c)
        one = summarise({c: 1})
        if one["resolved"] + one["refused"] + one["closed"] + one["open"] != 1:
            errs.append("class %s is not counted exactly once" % c)
    full = summarise({c: 1 for c in ALL_CLASSES})
    if full["total"] != len(ALL_CLASSES):
        errs.append("summary does not account for every class exactly once")
    if family(RESOLVED) != "UNCLASSIFIED":
        errs.append("the bare RESOLVED token is not correctly unclassified")
    return errs


if __name__ == "__main__":
    _e = selfcheck()
    for _c in sorted(ALL_CLASSES):
        print("  %-38s %-9s %s" % (_c, family(_c), DESCRIPTIONS[_c]))
    print("resolved=%d refused=%d closed=%d open=%d total=%d"
          % (len(RESOLVED_CLASSES), len(REFUSED_CLASSES), len(CLOSED_CLASSES),
             len(OPEN_CLASSES), len(ALL_CLASSES)))
    for _x in _e:
        print("  FAIL: %s" % _x)
    print("self-qualification: %d passed, %d failed" % (11 - len(_e), len(_e)))
    print("RESULT: %s" % ("PASS" if not _e else "FAIL"))
    raise SystemExit(1 if _e else 0)
