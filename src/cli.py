from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.extractors import extract_csv_records, extract_note_records
from src.linker import link_records
from src.merger import merge_groups
from src.normalizers import normalize_source_record
from src.projector import (
    ProjectionError,
    load_runtime_config,
    project_candidates,
)
from src.validator import ProjectionValidationError


def _unique_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warnings))


def _write_json(file_path: str | Path, data: object) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
        file.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Transform structured recruiter CSV data and unstructured "
            "recruiter notes into canonical candidate profiles."
        )
    )

    parser.add_argument(
        "--csv",
        help="Path to a recruiter CSV export.",
    )
    parser.add_argument(
        "--notes",
        help="Path to recruiter notes text file.",
    )
    parser.add_argument(
        "--config",
        help=(
            "Optional runtime output config. Without it, the CLI writes "
            "the full canonical schema."
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Path for the output JSON file.",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    csv_records = []
    note_records = []
    warnings: list[str] = []

    if args.csv:
        csv_records, csv_warnings = extract_csv_records(args.csv)
        warnings.extend(csv_warnings)

    if args.notes:
        note_records, note_warnings = extract_note_records(args.notes)
        warnings.extend(note_warnings)

    raw_records = csv_records + note_records
    normalized_records = [
        normalize_source_record(record)
        for record in raw_records
    ]

    groups = link_records(normalized_records)
    candidates = merge_groups(groups)

    for group in groups:
        warnings.extend(group.warnings)

    try:
        if args.config:
            config = load_runtime_config(args.config)
            output = project_candidates(candidates, config)
        else:
            output = [
                candidate.model_dump(mode="json")
                for candidate in candidates
            ]

        _write_json(args.out, output)

    except (
        OSError,
        ProjectionError,
        ProjectionValidationError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    for warning in _unique_warnings(warnings):
        print(f"WARNING: {warning}", file=sys.stderr)

    print(
        f"Wrote {len(output)} candidate profile(s) to {args.out}."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())