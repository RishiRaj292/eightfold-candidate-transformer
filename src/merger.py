from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Hashable

from src.models import (
    CandidateGroup,
    CanonicalCandidate,
    Evidence,
    Links,
    Location,
    Provenance,
    Skill,
)


SOURCE_PRIORITY = {
    "recruiter_csv": 2,
    "recruiter_notes": 1,
}


def _all_evidence(group: CandidateGroup) -> list[Evidence]:
    return [
        item
        for record in group.records
        for item in record.evidence
    ]


def _rank(item: Evidence) -> tuple[float, int, int, str]:
    return (
        -item.confidence,
        -SOURCE_PRIORITY.get(item.source, 0),
        item.order,
        item.record_id,
    )


def _best(items: list[Evidence]) -> Evidence:
    return min(items, key=_rank)


def _field_evidence(
    group: CandidateGroup,
    field_name: str,
) -> list[Evidence]:
    return [
        item
        for item in _all_evidence(group)
        if item.field == field_name
    ]


def _best_per_value(
    items: list[Evidence],
    key_fn: Callable[[Evidence], Hashable],
) -> list[Evidence]:
    buckets: dict[Hashable, list[Evidence]] = defaultdict(list)

    for item in items:
        buckets[key_fn(item)].append(item)

    selected = [_best(bucket) for bucket in buckets.values()]
    return sorted(selected, key=_rank)


def _capture(
    provenance: list[Provenance],
    confidences: list[float],
    item: Evidence,
    canonical_field: str,
) -> None:
    provenance.append(
        Provenance(
            field=canonical_field,
            source=item.source,
            method=item.method,
            record_id=item.record_id,
            confidence=item.confidence,
            raw_value=item.raw_value,
        )
    )
    confidences.append(item.confidence)


def _merge_string_list(
    group: CandidateGroup,
    evidence_field: str,
    canonical_field: str,
    provenance: list[Provenance],
    confidences: list[float],
) -> list[str]:
    items = _field_evidence(group, evidence_field)

    selected = _best_per_value(
        items,
        lambda item: str(item.value).casefold(),
    )

    values: list[str] = []

    for item in selected:
        values.append(str(item.value))
        _capture(provenance, confidences, item, canonical_field)

    return values


def _merge_location(
    group: CandidateGroup,
    provenance: list[Provenance],
    confidences: list[float],
) -> Location:
    location_items = _field_evidence(group, "location")

    result = {
        "city": None,
        "region": None,
        "country": None,
    }

    for component in result:
        candidates = [
            item
            for item in location_items
            if isinstance(item.value, dict)
            and item.value.get(component) is not None
        ]

        if not candidates:
            continue

        winner = _best(candidates)
        result[component] = str(winner.value[component])

        _capture(
            provenance,
            confidences,
            winner,
            f"location.{component}",
        )

    return Location(**result)


def _merge_links(
    group: CandidateGroup,
    provenance: list[Provenance],
    confidences: list[float],
) -> Links:
    result = Links()

    for field_name in ("linkedin", "github", "portfolio"):
        candidates = _field_evidence(group, field_name)

        if not candidates:
            continue

        winner = _best(candidates)
        setattr(result, field_name, str(winner.value))

        _capture(
            provenance,
            confidences,
            winner,
            f"links.{field_name}",
        )

    return result


def _merge_skills(
    group: CandidateGroup,
    provenance: list[Provenance],
    confidences: list[float],
) -> list[Skill]:
    items = _field_evidence(group, "skill")

    buckets: dict[str, list[Evidence]] = defaultdict(list)

    for item in items:
        buckets[str(item.value).casefold()].append(item)

    skills: list[Skill] = []

    for key in sorted(buckets):
        candidates = buckets[key]
        winner = _best(candidates)

        sources = sorted(
            {item.source for item in candidates},
            key=lambda source: (
                -SOURCE_PRIORITY.get(source, 0),
                source,
            ),
        )

        skills.append(
            Skill(
                name=str(winner.value),
                confidence=winner.confidence,
                sources=sources,
            )
        )

        _capture(provenance, confidences, winner, "skills")

    return skills


def _experience_key(item: Evidence) -> tuple[str, str, str, str]:
    value = item.value

    if not isinstance(value, dict):
        return ("", "", "", "")

    return (
        str(value.get("company") or "").casefold(),
        str(value.get("title") or "").casefold(),
        str(value.get("start") or ""),
        str(value.get("end") or ""),
    )


def _merge_experience(
    group: CandidateGroup,
    provenance: list[Provenance],
    confidences: list[float],
) -> list[dict[str, object]]:
    items = [
        item
        for item in _field_evidence(group, "experience")
        if isinstance(item.value, dict)
    ]

    selected = _best_per_value(items, _experience_key)
    experience: list[dict[str, object]] = []

    for item in selected:
        experience.append(dict(item.value))
        _capture(provenance, confidences, item, "experience")

    return experience


def _candidate_id(
    primary_email: str | None,
    full_name: str | None,
    group_id: str,
) -> str:
    seed = primary_email or f"{full_name or 'unknown'}|{group_id}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"cand_{digest}"


def merge_group(group: CandidateGroup) -> CanonicalCandidate:
    provenance: list[Provenance] = []
    confidences: list[float] = []

    full_name_items = _field_evidence(group, "full_name")
    full_name = None

    if full_name_items:
        winner = _best(full_name_items)
        full_name = str(winner.value)
        _capture(provenance, confidences, winner, "full_name")

    years_items = _field_evidence(group, "years_experience")
    years_experience = None

    if years_items:
        winner = _best(years_items)
        years_experience = float(winner.value)
        _capture(provenance, confidences, winner, "years_experience")

    emails = _merge_string_list(
        group,
        "email",
        "emails",
        provenance,
        confidences,
    )

    phones = _merge_string_list(
        group,
        "phone",
        "phones",
        provenance,
        confidences,
    )

    location = _merge_location(group, provenance, confidences)
    links = _merge_links(group, provenance, confidences)
    skills = _merge_skills(group, provenance, confidences)
    experience = _merge_experience(group, provenance, confidences)

    overall_confidence = (
        round(sum(confidences) / len(confidences), 2)
        if confidences
        else 0.0
    )

    return CanonicalCandidate(
        candidate_id=_candidate_id(
            primary_email=emails[0] if emails else None,
            full_name=full_name,
            group_id=group.group_id,
        ),
        full_name=full_name,
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        years_experience=years_experience,
        skills=skills,
        experience=experience,
        provenance=provenance,
        overall_confidence=overall_confidence,
    )


def merge_groups(groups: list[CandidateGroup]) -> list[CanonicalCandidate]:
    return [merge_group(group) for group in groups]