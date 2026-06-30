from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models import CanonicalCandidate, OutputField, RuntimeConfig

from src.validator import validate_projected_output

from src.normalizers import (
    normalize_date,
    normalize_email,
    normalize_phone,
    normalize_skill,
)


_MISSING = object()

_SEGMENT_PATTERN = re.compile(
    r"^(?P<name>[A-Za-z_]\w*)(?:\[(?P<index>\d*)\])?$"
)


class ProjectionError(ValueError):
    pass


def load_runtime_config(file_path: str | Path) -> RuntimeConfig:
    path = Path(file_path)

    try:
        raw_config = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProjectionError(
            f"Could not read config file: {path}"
        ) from error

    try:
        return RuntimeConfig.model_validate_json(raw_config)
    except ValidationError as error:
        raise ProjectionError(
            f"Invalid runtime config: {error}"
        ) from error


def _parse_source_path(path: str) -> list[tuple[str, str | None]]:
    segments: list[tuple[str, str | None]] = []

    for raw_segment in path.split("."):
        match = _SEGMENT_PATTERN.fullmatch(raw_segment)

        if match is None:
            raise ProjectionError(
                f"Unsupported source path segment: {raw_segment!r}"
            )

        segments.append(
            (
                match.group("name"),
                match.group("index"),
            )
        )

    return segments


def _resolve_source_path(data: Any, path: str) -> Any:
    segments = _parse_source_path(path)

    def walk(current: Any, index: int) -> Any:
        if index == len(segments):
            return current

        name, list_index = segments[index]

        if not isinstance(current, dict) or name not in current:
            return _MISSING

        value = current[name]

        if list_index is None:
            return walk(value, index + 1)

        if not isinstance(value, list):
            return _MISSING

        if list_index == "":
            result: list[Any] = []

            for item in value:
                resolved = walk(item, index + 1)

                if resolved is not _MISSING:
                    result.append(resolved)

            return result

        item_index = int(list_index)

        if item_index >= len(value):
            return _MISSING

        return walk(value[item_index], index + 1)

    return walk(data, 0)


def _set_output_path(
    output: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    parts = path.split(".")

    if not parts or any(not part for part in parts):
        raise ProjectionError(f"Invalid output path: {path!r}")

    current = output

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}

        if not isinstance(current[part], dict):
            raise ProjectionError(
                f"Cannot write nested path: {path!r}"
            )

        current = current[part]

    current[parts[-1]] = value


def _normalize_one(value: Any, rule: str) -> Any:
    if rule == "E164":
        return normalize_phone(value)

    if rule == "canonical":
        return normalize_skill(value)

    if rule == "email":
        return normalize_email(value)

    if rule == "date":
        return normalize_date(value)

    raise ProjectionError(f"Unsupported normalizer: {rule!r}")


def _apply_normalizer(value: Any, rule: str | None) -> Any:
    if rule is None:
        return value

    if isinstance(value, list):
        normalized_values: list[Any] = []

        for item in value:
            normalized = _normalize_one(item, rule)

            if normalized is not None:
                normalized_values.append(normalized)

        return normalized_values

    return _normalize_one(value, rule)


def _handle_missing(
    output: dict[str, Any],
    field: OutputField,
    config: RuntimeConfig,
) -> None:
    if field.required or config.on_missing == "error":
        raise ProjectionError(
            f"No value available for required field: {field.path!r}"
        )

    if config.on_missing == "null":
        _set_output_path(output, field.path, None)


def project_candidate(
    candidate: CanonicalCandidate,
    config: RuntimeConfig,
) -> dict[str, Any]:
    canonical = candidate.model_dump()
    output: dict[str, Any] = {}

    for field in config.fields:
        source_path = field.source_path or field.path

        value = _resolve_source_path(
            canonical,
            source_path,
        )

        if value is _MISSING or value is None:
            _handle_missing(output, field, config)
            continue

        value = _apply_normalizer(value, field.normalize)

        if value is None:
            _handle_missing(output, field, config)
            continue

        _set_output_path(output, field.path, value)

    if config.include_confidence:
        output["overall_confidence"] = candidate.overall_confidence

    if config.include_provenance:
        output["provenance"] = [
            item.model_dump()
            for item in candidate.provenance
        ]
    validate_projected_output(output, config)
    return output


def project_candidates(
    candidates: list[CanonicalCandidate],
    config: RuntimeConfig,
) -> list[dict[str, Any]]:
    return [
        project_candidate(candidate, config)
        for candidate in candidates
    ]