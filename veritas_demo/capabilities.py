"""Public capability discovery for Veritas.

The question ``find`` answers is *"has this already been built, somewhere?"* — and
the honest answer is almost never a yes or a no. It is a **candidate lead**: a
lexical near-match that a human should look at. This module is built around that
distinction.

Three things it deliberately does not do:

1. **It does not rank by quality.** Ranking reflects vocabulary overlap, nothing
   more. A high score is not a recommendation.
2. **It does not treat absence as proof.** ``NO_MATCH`` means *no term of this
   request appears in the registries searched*. The registry may be incomplete.
   That distinction is the whole reason this exists.
3. **It does not encode one corpus.** A registry is whatever the caller supplies.
   The bundled example registry is synthetic demo data, clearly labelled, and
   exists so ``find`` is demonstrable immediately.

A provider is anything that yields capability records. v1 ships one
(``LocalJsonRegistryProvider``) but the seam is ``CapabilityRegistryProvider``,
so a URL-hosted registry, a package entry point, or a private-estate adapter can
be added without touching this module.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Protocol, runtime_checkable

__all__ = [
    "CapabilityRecord",
    "CapabilityRegistryProvider",
    "LocalJsonRegistryProvider",
    "NO_MATCH",
    "PARTIAL_MATCH",
    "MULTIPLE_CANDIDATES",
    "RegistryUnavailable",
    "load_registries",
    "query",
    "search",
]


# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #

NO_MATCH = "NO_MATCH"
PARTIAL_MATCH = "PARTIAL_MATCH"
MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"

#: Fields a term can match, weighted by how strongly a hit implies a candidate.
#: A capability NAMED for the request is a stronger signal than one that mentions
#: the request in passing.
_FIELD_WEIGHTS = {
    "id": 0.30,
    "name": 0.30,
    "aliases": 0.30,
    "terms": 0.10,
    "description": 0.10,
    "evidence_notes": 0.10,
    "source": 0.10,
}

#: Below this many distinct query terms, a candidate is not reported at all. A
#: single word-boundary hit is noise, and reporting noise crowds out refusal.
MIN_SIGNIFICANT_TERMS = 2

_STOPWORDS = frozenset({
    "a", "an", "the", "of", "and", "or", "to", "for", "in", "on", "with", "as",
    "is", "are", "was", "were", "can", "does", "do", "did", "how", "what",
    "which", "who", "i", "we", "it", "this", "that", "these", "those", "be",
    "been", "by", "from", "into", "use", "using", "used", "need", "needs",
    "have", "has", "there", "any", "some", "me", "my", "our", "their",
})


class RegistryUnavailable(RuntimeError):
    """A configured registry could not be read.

    Distinct from NO_MATCH on purpose. An unreadable registry is a failure to
    answer; NO_MATCH is an answer. Silently treating one as the other would let
    a typo in a path look exactly like a capability gap.
    """


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CapabilityRecord:
    """One capability a caller has registered.

    Fields beyond the documented core are preserved in ``extra`` rather than
    rejected, so a caller can extend the schema without forking this module.
    """

    id: str
    name: str = ""
    description: str = ""
    terms: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    status: str = "unknown"
    source: str = ""
    callable_now: bool | None = None
    evidence_notes: str = ""
    verification: tuple[str, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)

    #: Field name -> text to match against.
    def matchable(self) -> dict[str, str]:
        return {
            "id": self.id,
            "name": self.name,
            "aliases": " ".join(self.aliases),
            "terms": " ".join(self.terms),
            "description": self.description,
            "evidence_notes": self.evidence_notes,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CapabilityRecord:
        known = {
            "id", "name", "description", "terms", "aliases", "status", "source",
            "callable", "evidence_notes", "verification",
        }
        return cls(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            description=str(raw.get("description", "")),
            terms=_as_str_tuple(raw.get("terms")),
            aliases=_as_str_tuple(raw.get("aliases")),
            status=str(raw.get("status", "unknown")),
            source=str(raw.get("source", "")),
            callable_now=raw.get("callable") if isinstance(raw.get("callable"), bool) else None,
            evidence_notes=str(raw.get("evidence_notes", "")),
            verification=_as_str_tuple(raw.get("verification")),
            extra={k: v for k, v in raw.items() if k not in known},
        )


def _as_str_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return (str(value),)


# --------------------------------------------------------------------------- #
# providers
# --------------------------------------------------------------------------- #


@runtime_checkable
class CapabilityRegistryProvider(Protocol):
    """Anything that can supply capability records.

    v1 provides a local JSON file. The protocol exists so that a URL registry, a
    Python package's entry points, or a private-estate adapter can be added
    later without the search or output code changing.
    """

    name: str

    def load(self) -> list[CapabilityRecord]: ...


@dataclass
class LocalJsonRegistryProvider:
    """A capability registry stored as a local JSON document.

    The format is deliberately small::

        {
          "registry": "my-registry",
          "version": "1",
          "capabilities": [
            {
              "id": "EVIDENCE_VERIFICATION",
              "name": "evidence verification",
              "description": "...",
              "terms": ["verify", "check", "audit"],
              "status": "implemented",
              "source": "https://github.com/...",
              "callable": true,
              "evidence_notes": "covered by tests/test_x.py",
              "verification": ["tests/test_x.py"]
            }
          ]
        }

    Unknown keys on a record are preserved, not rejected.
    """

    path: Path
    name: str = ""

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if not self.name:
            self.name = self.path.name

    def load(self) -> list[CapabilityRecord]:
        try:
            raw_text = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RegistryUnavailable(
                f"registry {self.name!r}: cannot read {self.path}: {exc}"
            ) from exc
        try:
            document = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise RegistryUnavailable(
                f"registry {self.name!r}: {self.path} is not valid JSON: {exc}"
            ) from exc
        if not isinstance(document, dict) or not isinstance(
            document.get("capabilities"), list
        ):
            raise RegistryUnavailable(
                f"registry {self.name!r}: {self.path} has no 'capabilities' list"
            )
        records = []
        for index, entry in enumerate(document["capabilities"]):
            if not isinstance(entry, dict):
                raise RegistryUnavailable(
                    f"registry {self.name!r}: entry {index} is not an object"
                )
            records.append(CapabilityRecord.from_dict(entry))
        return records


# --------------------------------------------------------------------------- #
# matching
# --------------------------------------------------------------------------- #


def _terms(request: str) -> set[str]:
    """Content words from a free-text request.

    Deliberately simple. A synonym index would be a second subsystem, and an
    unexamined one. Over-narrow matching surfaces as NO_MATCH, which is the safe
    direction: it sends the caller to read the registry rather than trusting a
    guess.
    """
    words = re.split(r"[^A-Za-z0-9_]+", (request or "").lower())
    return {w for w in words if w and w not in _STOPWORDS}


def _score(record: CapabilityRecord, terms: set[str]) -> tuple[float, dict[str, list[str]]]:
    """How strongly a record matches, and on which fields.

    Substring matching is deliberately NOT used. An early version matched
    ``capability`` inside unrelated prose and scored a nonsense query at 0.10,
    which made NO_MATCH unreachable — and NO_MATCH being unreachable is the one
    failure this surface exists to prevent. Terms match as whole words only.
    """
    if not terms:
        return 0.0, {}
    hits: dict[str, list[str]] = {}
    for field_name, text in record.matchable().items():
        if not text:
            continue
        found = sorted(
            t for t in terms if re.search(rf"\b{re.escape(t)}\b", text.lower())
        )
        if found:
            hits[field_name] = found

    distinct = {t for terms_found in hits.values() for t in terms_found}
    if len(distinct) < MIN_SIGNIFICANT_TERMS:
        return 0.0, {}

    score = sum(
        _FIELD_WEIGHTS.get(f, 0.0) * len(hits[f]) for f in hits
    )
    return min(1.0, score), hits


#: The single sentence every result must carry. A ranking that could be mistaken
#: for a recommendation is a defect, so the caveat travels with the data.
LEXICAL_RANKING_CAVEAT = (
    "Ranking reflects lexical term overlap with this registry's vocabulary. It is "
    "NOT evidence that the capability satisfies the request, and NOT a "
    "recommendation. Read the record before relying on it."
)

NO_MATCH_CAVEAT = (
    "No query term appeared in the registries searched. That is a statement about "
    "those registries, not proof that the capability does not exist: a registry "
    "may be incomplete, or may describe the capability in other words."
)


# --------------------------------------------------------------------------- #
# query
# --------------------------------------------------------------------------- #


def search(
    request: str,
    providers: Iterable[CapabilityRegistryProvider],
    *,
    limit: int = 6,
) -> dict[str, Any]:
    """Search every supplied registry and return qualified candidate leads."""
    terms = _terms(request)
    provider_list = list(providers)
    if not terms:
        return {
            "query": request,
            "verdict": NO_MATCH,
            "candidates": [],
            "registries_searched": [p.name for p in provider_list],
            "qualifier": "the request contained no searchable terms",
            "note": NO_MATCH_CAVEAT,
        }

    scored: list[tuple[float, CapabilityRecord, dict[str, list[str]], str]] = []
    for provider in provider_list:
        for record in provider.load():
            score, hits = _score(record, terms)
            if score > 0:
                scored.append((score, record, hits, provider.name))

    # Sort by score, then by id, so equal scores do not reorder between runs.
    scored.sort(key=lambda t: (-t[0], t[1].id, t[3]))

    searched = [p.name for p in provider_list]
    if not scored:
        return {
            "query": request,
            "verdict": NO_MATCH,
            "candidates": [],
            "registries_searched": searched,
            "qualifier": (
                "no term of this request matched a registered capability in the "
                "registries searched"
            ),
            "note": NO_MATCH_CAVEAT,
        }

    candidates = []
    for score, record, hits, registry_name in scored[:limit]:
        entry: dict[str, Any] = {
            "candidate_id": record.id,
            "name": record.name,
            "lexical_score": round(score, 3),
            "matched_fields": hits,
            "matched_terms": sorted({t for f in hits.values() for t in f}),
            "source_registry": registry_name,
            "status": record.status,
        }
        if record.source:
            entry["source"] = record.source
        if record.callable_now is not None:
            entry["callable"] = record.callable_now
        if record.evidence_notes:
            entry["evidence_notes"] = record.evidence_notes
        if record.verification:
            entry["verification"] = list(record.verification)
        if record.extra:
            entry["extra"] = record.extra
        candidates.append(entry)

    top = scored[0][0]
    tied = [s for s in scored if s[0] >= top * 0.8]
    verdict = MULTIPLE_CANDIDATES if len(tied) > 1 else PARTIAL_MATCH

    return {
        "query": request,
        "verdict": verdict,
        "candidates": candidates,
        "registries_searched": searched,
        "top_score": round(top, 3),
        "qualifier": (
            f"{len(scored)} candidate lead(s); the top {len(tied)} are within 20% of "
            "each other on lexical score alone"
        ),
        "note": LEXICAL_RANKING_CAVEAT,
    }


def query(request: str, providers: Iterable[CapabilityRegistryProvider]) -> dict[str, Any]:
    """Backwards-compatible alias for :func:`search`."""
    return search(request, providers)


# --------------------------------------------------------------------------- #
# registry resolution
# --------------------------------------------------------------------------- #


#: Bundled example registry, shipped so `find` works immediately after install.
BUNDLED_EXAMPLE = Path(__file__).parent / "example_capability_registry.json"

ENV_REGISTRY = "VERITAS_CAPABILITY_REGISTRY"


def load_registries(
    explicit: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
    include_example: bool = True,
) -> list[CapabilityRegistryProvider]:
    """Resolve which registries to search, in order of precedence.

    1. ``explicit`` — a path passed on the command line
    2. ``VERITAS_CAPABILITY_REGISTRY`` — a path, or ``os.pathsep``-separated paths
    3. the bundled synthetic example registry

    Precedence is not merging: if an explicit registry is given, the bundled
    example is *not* searched alongside it. A caller who points at their own
    registry means it, and silently mixing in demo data would corrupt the
    answer.

    An explicit registry that cannot be read raises. It does not fall back to the
    example — a typo in a path must not look like a working query against
    different data.
    """
    environment = os.environ if env is None else env
    providers: list[CapabilityRegistryProvider] = []

    if explicit is not None:
        return [LocalJsonRegistryProvider(Path(explicit))]

    configured = environment.get(ENV_REGISTRY, "").strip()
    if configured:
        for chunk in configured.split(os.pathsep):
            if chunk.strip():
                providers.append(LocalJsonRegistryProvider(Path(chunk.strip())))
        return providers

    if include_example:
        providers.append(LocalJsonRegistryProvider(BUNDLED_EXAMPLE))
    return providers
