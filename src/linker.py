from __future__ import annotations

from collections import defaultdict
from itertools import combinations

from src.models import CandidateGroup, SourceRecord


def _field_values(record: SourceRecord, field_name: str) -> set[str]:
    values: set[str] = set()

    for item in record.evidence:
        if item.field != field_name:
            continue

        if isinstance(item.value, str) and item.value.strip():
            values.add(item.value.strip())

    return values


def _normalized_name(record: SourceRecord) -> str | None:
    names = _field_values(record, "full_name")

    if not names:
        return None

    name = sorted(names)[0]
    return " ".join(name.casefold().split())


def _has_identity_conflict(
    left: SourceRecord,
    right: SourceRecord,
    match_type: str,
) -> bool:
    left_name = _normalized_name(left)
    right_name = _normalized_name(right)

    if left_name and right_name and left_name != right_name:
        return True

    left_emails = _field_values(left, "email")
    right_emails = _field_values(right, "email")

    left_phones = _field_values(left, "phone")
    right_phones = _field_values(right, "phone")

    if match_type == "phone":
        if left_emails and right_emails and left_emails.isdisjoint(right_emails):
            return True

    if match_type == "email":
        if left_phones and right_phones and left_phones.isdisjoint(right_phones):
            return True

    return False


def _find(parent: list[int], node: int) -> int:
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]

    return node


def _union(parent: list[int], left: int, right: int) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)

    if left_root == right_root:
        return

    if left_root < right_root:
        parent[right_root] = left_root
    else:
        parent[left_root] = right_root


def _add_candidate_pairs(
    index: dict[str, list[int]],
    records: list[SourceRecord],
    parent: list[int],
    match_type: str,
    warnings_by_record: dict[int, list[str]],
) -> None:
    for key in sorted(index):
        record_indexes = index[key]

        for left_index, right_index in combinations(record_indexes, 2):
            left = records[left_index]
            right = records[right_index]

            if _has_identity_conflict(left, right, match_type):
                warning = (
                    f"Did not link {left.record_id} and {right.record_id}: "
                    f"conflicting identifiers despite shared {match_type}."
                )
                warnings_by_record[left_index].append(warning)
                warnings_by_record[right_index].append(warning)
                continue

            _union(parent, left_index, right_index)


def link_records(records: list[SourceRecord]) -> list[CandidateGroup]:
    parent = list(range(len(records)))
    warnings_by_record: dict[int, list[str]] = defaultdict(list)

    email_index: dict[str, list[int]] = defaultdict(list)
    phone_index: dict[str, list[int]] = defaultdict(list)
    name_index: dict[str, list[int]] = defaultdict(list)

    for record_index, record in enumerate(records):
        for email in _field_values(record, "email"):
            email_index[email].append(record_index)

        for phone in _field_values(record, "phone"):
            phone_index[phone].append(record_index)

        name = _normalized_name(record)
        if name is not None:
            name_index[name].append(record_index)

    _add_candidate_pairs(
        email_index,
        records,
        parent,
        "email",
        warnings_by_record,
    )

    _add_candidate_pairs(
        phone_index,
        records,
        parent,
        "phone",
        warnings_by_record,
    )

    for name, record_indexes in name_index.items():
        if len(record_indexes) < 2:
            continue

        groups = {_find(parent, record_index) for record_index in record_indexes}

        if len(groups) > 1:
            warning = (
                f"Same-name records for {name!r} were not linked without "
                "a matching normalized email or phone."
            )

            for record_index in record_indexes:
                warnings_by_record[record_index].append(warning)

    grouped_indexes: dict[int, list[int]] = defaultdict(list)

    for record_index in range(len(records)):
        grouped_indexes[_find(parent, record_index)].append(record_index)

    groups: list[CandidateGroup] = []

    for group_number, root_index in enumerate(sorted(grouped_indexes), start=1):
        record_indexes = grouped_indexes[root_index]
        group_records = [records[index] for index in record_indexes]

        group_warnings: list[str] = []

        for record_index in record_indexes:
            group_warnings.extend(records[record_index].warnings)
            group_warnings.extend(warnings_by_record[record_index])

        groups.append(
            CandidateGroup(
                group_id=f"group-{group_number:03d}",
                records=group_records,
                warnings=list(dict.fromkeys(group_warnings)),
            )
        )

    return groups