from __future__ import annotations

from typing import Any

from src.models import RuntimeConfig


_MISSING = object()


class ProjectionValidationError(ValueError):
    pass


def _read_output_path(
    data: dict[str, Any],
    path: str,
) -> Any:
    current: Any = data

    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING

        current = current[part]

    return current


def _matches_type(
    value: Any,
    expected_type: str,
) -> bool:
    if expected_type == "string":
        return isinstance(value, str)

    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    if expected_type == "boolean":
        return isinstance(value, bool)

    if expected_type == "string[]":
        return isinstance(value, list) and all(
            isinstance(item, str)
            for item in value
        )

    if expected_type == "object":
        return isinstance(value, dict)

    if expected_type == "object[]":
        return isinstance(value, list) and all(
            isinstance(item, dict)
            for item in value
        )

    return False


def validate_projected_output(
    projected: dict[str, Any],
    config: RuntimeConfig,
) -> None:
    errors: list[str] = []

    for field in config.fields:
        value = _read_output_path(projected, field.path)

        if value is _MISSING:
            if field.required:
                errors.append(
                    f"Required field {field.path!r} is missing."
                )
            elif config.on_missing == "null":
                errors.append(
                    f"Optional field {field.path!r} is missing; "
                    "config requires null."
                )
            continue

        if value is None:
            if field.required:
                errors.append(
                    f"Required field {field.path!r} is null."
                )
            elif config.on_missing == "omit":
                errors.append(
                    f"Optional field {field.path!r} is null; "
                    "config requires omission."
                )
            continue

        if not _matches_type(value, field.type):
            errors.append(
                f"Field {field.path!r} must be {field.type}; "
                f"got {type(value).__name__}."
            )

    if config.include_confidence:
        confidence = projected.get("overall_confidence", _MISSING)

        if confidence is _MISSING:
            errors.append("overall_confidence is required by config.")
        elif (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0.0 <= confidence <= 1.0
        ):
            errors.append(
                "overall_confidence must be a number between 0 and 1."
            )

    if config.include_provenance:
        provenance = projected.get("provenance", _MISSING)

        if provenance is _MISSING:
            errors.append("provenance is required by config.")
        elif not (
            isinstance(provenance, list)
            and all(isinstance(item, dict) for item in provenance)
        ):
            errors.append("provenance must be a list of objects.")

    if errors:
        raise ProjectionValidationError(" ".join(errors))