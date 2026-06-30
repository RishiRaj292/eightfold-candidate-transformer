from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from src.models import Evidence, SourceRecord


EMAIL_PATTERN = re.compile(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b")

CANDIDATE_PATTERN = re.compile(
    r"(?im)^\s*Candidate\s*:\s*(?P<name>.+?)\s*$"
)

LOCATION_PATTERN = re.compile(
    r"\bbased in\s+(?P<location>.+?)(?=\s+and\s+can\s+be\s+reached\b|[.\n]|$)",
    re.IGNORECASE,
)

EXPERIENCE_PATTERN = re.compile(
    r"\bjoined\s+(?P<company>.+?)\s+as\s+a[n]?\s+"
    r"(?P<title>.+?)\s+in\s+"
    r"(?P<start>(?:[A-Za-z]{3,9}\s+\d{4}|\d{4}[-/]\d{1,2}))",
    re.IGNORECASE,
)

YEARS_PATTERN = re.compile(
    r"\b(?:about|around|over)?\s*(?P<years>\d+(?:\.\d+)?)\s+"
    r"years?\s+of\s+experience\b",
    re.IGNORECASE,
)

SKILLS_PATTERN = re.compile(
    r"\b(?:strong in|skills mentioned\s*:)\s*(?P<skills>[^.\n]+)",
    re.IGNORECASE,
)

LINKEDIN_PATTERN = re.compile(
    r"https?://(?:www\.)?linkedin\.com/[^\s]+",
    re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"\b(?:can be reached at|phone(?:\s+is)?|contact(?:\s+number)?"
    r"(?:\s+is)?)\s*(?P<phone>\+?\d[\d\s().-]{2,}\d|\d{4,})",
    re.IGNORECASE,
)


def _text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _add_evidence(
    evidence: list[Evidence],
    *,
    field: str,
    value: Any,
    source: str,
    method: str,
    confidence: float,
    record_id: str,
    order: int,
) -> None:
    if isinstance(value, str) and not value.strip():
        return

    if value is None:
        return

    evidence.append(
        Evidence(
            field=field,
            value=value,
            raw_value=value,
            source=source,
            method=method,
            confidence=confidence,
            record_id=record_id,
            order=order,
        )
    )


def extract_csv_records(
    file_path: str | Path,
) -> tuple[list[SourceRecord], list[str]]:
    path = Path(file_path)
    records: list[SourceRecord] = []
    warnings: list[str] = []

    if not path.exists():
        return [], [f"CSV source not found: {path}"]

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                return [], [f"CSV source has no header row: {path}"]

            for row_index, row in enumerate(reader, start=1):
                record_id = _text(row.get("candidate_ref")) or f"csv-row-{row_index}"
                evidence: list[Evidence] = []
                record_warnings: list[str] = []
                base_order = row_index * 100

                _add_evidence(
                    evidence,
                    field="full_name",
                    value=_text(row.get("full_name")),
                    source="recruiter_csv",
                    method="exact_csv_column",
                    confidence=0.90,
                    record_id=record_id,
                    order=base_order + 1,
                )

                _add_evidence(
                    evidence,
                    field="email",
                    value=_text(row.get("email")),
                    source="recruiter_csv",
                    method="exact_csv_column",
                    confidence=0.90,
                    record_id=record_id,
                    order=base_order + 2,
                )

                _add_evidence(
                    evidence,
                    field="phone",
                    value=_text(row.get("phone")),
                    source="recruiter_csv",
                    method="exact_csv_column",
                    confidence=0.90,
                    record_id=record_id,
                    order=base_order + 3,
                )

                _add_evidence(
                    evidence,
                    field="location",
                    value=_text(row.get("location")),
                    source="recruiter_csv",
                    method="exact_csv_column",
                    confidence=0.90,
                    record_id=record_id,
                    order=base_order + 4,
                )

                _add_evidence(
                    evidence,
                    field="years_experience",
                    value=_text(row.get("years_experience")),
                    source="recruiter_csv",
                    method="exact_csv_column",
                    confidence=0.90,
                    record_id=record_id,
                    order=base_order + 5,
                )

                _add_evidence(
                    evidence,
                    field="skills",
                    value=_text(row.get("skills")),
                    source="recruiter_csv",
                    method="exact_csv_column",
                    confidence=0.90,
                    record_id=record_id,
                    order=base_order + 6,
                )

                experience = {
                    "company": _text(row.get("current_company")),
                    "title": _text(row.get("title")),
                    "start": _text(row.get("start_date")),
                    "end": None,
                    "summary": None,
                }

                if any(experience.values()):
                    _add_evidence(
                        evidence,
                        field="experience",
                        value=experience,
                        source="recruiter_csv",
                        method="exact_csv_columns",
                        confidence=0.90,
                        record_id=record_id,
                        order=base_order + 7,
                    )

                if not evidence:
                    record_warnings.append("CSV row had no usable values.")

                records.append(
                    SourceRecord(
                        source="recruiter_csv",
                        record_id=record_id,
                        evidence=evidence,
                        warnings=record_warnings,
                    )
                )

    except (OSError, csv.Error) as error:
        warnings.append(f"Could not read CSV source {path}: {error}")

    return records, warnings


def _split_note_blocks(text: str) -> list[str]:
    return [
        block.strip()
        for block in re.split(r"\n\s*-{3,}\s*\n", text.strip())
        if block.strip()
    ]


def _split_note_skills(value: str) -> list[str]:
    cleaned = re.sub(r"\band\b", ",", value, flags=re.IGNORECASE)

    return [
        item.strip()
        for item in re.split(r"[,;|]", cleaned)
        if item.strip()
    ]


def extract_note_records(
    file_path: str | Path,
) -> tuple[list[SourceRecord], list[str]]:
    path = Path(file_path)
    records: list[SourceRecord] = []
    warnings: list[str] = []

    if not path.exists():
        return [], [f"Recruiter notes source not found: {path}"]

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        return [], [f"Could not read recruiter notes {path}: {error}"]

    if not text.strip():
        return [], [f"Recruiter notes source is empty: {path}"]

    for block_index, block in enumerate(_split_note_blocks(text), start=1):
        record_id = f"notes-block-{block_index}"
        evidence: list[Evidence] = []
        record_warnings: list[str] = []
        base_order = block_index * 100

        name_match = CANDIDATE_PATTERN.search(block)

        if name_match:
            name = name_match.group("name").strip()

            _add_evidence(
                evidence,
                field="full_name",
                value=name,
                source="recruiter_notes",
                method="labeled_note_field",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 1,
            )
        else:
            record_warnings.append("No labeled candidate name found in notes block.")

        for email_index, email in enumerate(EMAIL_PATTERN.findall(block), start=1):
            _add_evidence(
                evidence,
                field="email",
                value=email,
                source="recruiter_notes",
                method="regex_note_extraction",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 10 + email_index,
            )

        for phone_index, match in enumerate(PHONE_PATTERN.finditer(block), start=1):
            _add_evidence(
                evidence,
                field="phone",
                value=match.group("phone").strip(),
                source="recruiter_notes",
                method="contextual_regex_extraction",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 20 + phone_index,
            )

        location_match = LOCATION_PATTERN.search(block)
        if location_match:
            _add_evidence(
                evidence,
                field="location",
                value=location_match.group("location").strip(),
                source="recruiter_notes",
                method="contextual_regex_extraction",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 30,
            )

        years_match = YEARS_PATTERN.search(block)
        if years_match:
            _add_evidence(
                evidence,
                field="years_experience",
                value=years_match.group("years"),
                source="recruiter_notes",
                method="contextual_regex_extraction",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 40,
            )

        skills_match = SKILLS_PATTERN.search(block)
        if skills_match:
            for skill_index, skill in enumerate(
                _split_note_skills(skills_match.group("skills")),
                start=1,
            ):
                _add_evidence(
                    evidence,
                    field="skill",
                    value=skill,
                    source="recruiter_notes",
                    method="contextual_regex_extraction",
                    confidence=0.65,
                    record_id=record_id,
                    order=base_order + 50 + skill_index,
                )

        experience_match = EXPERIENCE_PATTERN.search(block)
        if experience_match:
            experience = {
                "company": experience_match.group("company").strip(),
                "title": experience_match.group("title").strip(),
                "start": experience_match.group("start").strip(),
                "end": None,
                "summary": None,
            }

            _add_evidence(
                evidence,
                field="experience",
                value=experience,
                source="recruiter_notes",
                method="contextual_regex_extraction",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 70,
            )

        for link_index, link in enumerate(LINKEDIN_PATTERN.findall(block), start=1):
            _add_evidence(
                evidence,
                field="linkedin",
                value=link.rstrip(".,)"),
                source="recruiter_notes",
                method="regex_note_extraction",
                confidence=0.65,
                record_id=record_id,
                order=base_order + 80 + link_index,
            )

        if not evidence:
            record_warnings.append("No usable evidence extracted from notes block.")

        records.append(
            SourceRecord(
                source="recruiter_notes",
                record_id=record_id,
                evidence=evidence,
                warnings=record_warnings,
            )
        )

    return records, warnings