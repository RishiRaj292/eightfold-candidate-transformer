from __future__ import annotations

import re

import phonenumbers
from dateutil import parser as date_parser
from src.models import Evidence, SourceRecord

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "py": "Python",
    "python": "Python",
    "fastapi": "FastAPI",
    "redis": "Redis",
    "sql": "SQL",
    "java": "Java",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
}

CITY_ALIASES = {
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "pune": "Pune",
}

COUNTRY_ALIASES = {
    "india": "IN",
    "in": "IN",
}


def clean_text(value: object) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def normalize_email(value: object) -> str | None:
    email = clean_text(value)

    if email is None:
        return None

    email = email.lower()
    return email if EMAIL_PATTERN.fullmatch(email) else None


def normalize_phone(
    value: object,
    default_region: str | None = None,
) -> str | None:
    phone = clean_text(value)

    if phone is None:
        return None

    try:
        parsed = phonenumbers.parse(phone, default_region)

        if not phonenumbers.is_possible_number(parsed):
            return None

        if not phonenumbers.is_valid_number(parsed):
            return None

        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164,
        )
    except phonenumbers.NumberParseException:
        return None


def normalize_date(value: object) -> str | None:
    text = clean_text(value)

    if text is None:
        return None

    year_month = re.fullmatch(r"(\d{4})[-/](\d{1,2})", text)
    if year_month:
        year, month = year_month.groups()

        if 1 <= int(month) <= 12:
            return f"{year}-{int(month):02d}"

        return None

    try:
        parsed = date_parser.parse(text, fuzzy=False)
        return f"{parsed.year:04d}-{parsed.month:02d}"
    except (ValueError, OverflowError):
        return None


def normalize_skill(value: object) -> str | None:
    skill = clean_text(value)

    if skill is None:
        return None

    key = skill.lower()
    return SKILL_ALIASES.get(key, skill)


def split_skills(value: object) -> list[str]:
    text = clean_text(value)

    if text is None:
        return []

    return [
        item.strip()
        for item in re.split(r"[;,|]", text)
        if item.strip()
    ]


def normalize_skills(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        skill = normalize_skill(value)

        if skill is None:
            continue

        key = skill.lower()

        if key not in seen:
            seen.add(key)
            result.append(skill)

    return result


def normalize_country(value: object) -> str | None:
    country = clean_text(value)

    if country is None:
        return None

    key = country.lower()

    if key in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[key]

    if len(country) == 2 and country.isalpha():
        return country.upper()

    return None


def normalize_location(value: object) -> dict[str, str | None]:
    empty_location = {
        "city": None,
        "region": None,
        "country": None,
    }

    text = clean_text(value)

    if text is None:
        return empty_location

    parts = [part.strip() for part in text.split(",") if part.strip()]

    if not parts:
        return empty_location

    country = normalize_country(parts[-1])

    if country is not None:
        parts = parts[:-1]

    city = None
    region = None

    if len(parts) >= 1:
        city_value = parts[0]
        city = CITY_ALIASES.get(city_value.lower(), city_value)

    if len(parts) >= 2:
        region = parts[1]

    return {
        "city": city,
        "region": region,
        "country": country,
    }

def normalize_source_record(record: SourceRecord) -> SourceRecord:
    normalized_evidence: list[Evidence] = []
    warnings = list(record.warnings)

    location_country: str | None = None

    for item in record.evidence:
        if item.field != "location":
            continue

        location = normalize_location(item.value)
        location_country = location["country"]

        if any(location.values()):
            break

    for item in record.evidence:
        normalized_value = item.value
        normalized_field = item.field

        if item.field == "email":
            normalized_value = normalize_email(item.value)

        elif item.field == "phone":
            normalized_value = normalize_phone(
                item.value,
                default_region=location_country,
            )

        elif item.field == "location":
            normalized_value = normalize_location(item.value)

            if not any(normalized_value.values()):
                normalized_value = None

        elif item.field == "years_experience":
            try:
                normalized_value = float(str(item.value).strip())
            except ValueError:
                normalized_value = None

        elif item.field == "skills":
            normalized_field = "skill"

            for skill in normalize_skills(split_skills(item.value)):
                normalized_evidence.append(
                    item.model_copy(
                        update={
                            "field": "skill",
                            "value": skill,
                            "raw_value": item.value,
                        }
                    )
                )

            continue

        elif item.field == "skill":
            normalized_value = normalize_skill(item.value)

        elif item.field == "experience":
            experience = dict(item.value)

            experience["company"] = clean_text(experience.get("company"))
            experience["title"] = clean_text(experience.get("title"))
            experience["start"] = normalize_date(experience.get("start"))
            experience["end"] = normalize_date(experience.get("end"))
            experience["summary"] = clean_text(experience.get("summary"))

            normalized_value = experience

        elif item.field in {"full_name", "linkedin"}:
            normalized_value = clean_text(item.value)

        if normalized_value is None:
            warnings.append(
                f"{record.record_id}: omitted invalid {item.field!r} value "
                f"{item.raw_value!r}."
            )
            continue

        normalized_evidence.append(
            item.model_copy(
                update={
                    "field": normalized_field,
                    "value": normalized_value,
                    "raw_value": item.raw_value,
                }
            )
        )

    return record.model_copy(
        update={
            "evidence": normalized_evidence,
            "warnings": warnings,
        }
    )