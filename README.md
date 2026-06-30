# Eightfold Candidate Profile Transformer

A deterministic Python CLI that combines structured recruiter CSV data and unstructured recruiter notes into clean, canonical candidate profiles.

The pipeline is evidence-first: each extractor emits source-attributed evidence; normalization, identity linking, deterministic merge, config projection, and validation then produce JSON output.

## What It Covers

* **Structured source:** recruiter CSV export
* **Unstructured source:** recruiter notes (`.txt`)
* Email, phone, date, location, and skill normalization
* Safe identity linking across sources
* Deterministic merge, confidence, and provenance
* Runtime-configured output reshaping without code changes
* Dynamic validation of custom output
* Graceful handling of malformed or missing values

## Pipeline

```text
CSV + Recruiter Notes
→ Evidence Extraction
→ Field Normalization
→ Identity Linking
→ Trust-Based Merge + Confidence
→ Config Projection
→ Validation
→ JSON Output
```

## Project Structure

```text
eightfold-candidate-transformer/
├── src/
│   ├── cli.py            # CLI orchestration
│   ├── models.py         # Pydantic models and runtime config schema
│   ├── extractors.py     # CSV and recruiter-note extraction
│   ├── normalizers.py    # Email, phone, date, skill, location normalization
│   ├── linker.py         # Safe identity linking
│   ├── merger.py         # Deterministic merge, provenance, confidence
│   ├── projector.py      # Runtime-configurable output projection
│   └── validator.py      # Dynamic projected-output validation
├── samples/
│   ├── recruiter_export.csv
│   ├── recruiter_notes.txt
│   └── custom_config.json
├── outputs/
│   ├── default_output.json
│   └── custom_output.json
├── tests/
│   └── test_pipeline.py
├── requirements.txt
└── pytest.ini
```

## Normalization Rules

* **Emails:** lowercase and deduplicated.
* **Phones:** converted to E.164 only when valid and country context is available.
* **Dates:** standardized to `YYYY-MM`.
* **Locations:** structured as `{ city, region, country }`; for example, `Bangalore` becomes `Bengaluru`, and India becomes `IN`.
* **Skills:** aliases are canonicalized, for example `JS → JavaScript`.
* Invalid values are omitted rather than guessed or invented.

## Identity Linking

Records are linked using normalized identifiers in this order:

```text
email → phone
```

A shared identifier is rejected when another available identifier conflicts. Same-name-only records are **not** auto-merged; they remain separate and emit a warning.

## Merge, Confidence, and Provenance

For scalar fields such as `full_name` and `years_experience`, the winner is selected deterministically:

```text
highest confidence → source priority → stable input order
```

Source priority:

```text
recruiter_csv > recruiter_notes
```

Current confidence assignments:

```text
Exact CSV field:                 0.90
Labeled / regex note extraction: 0.65
```

List fields such as emails, phones, skills, and experience retain valid normalized unique values. Every accepted canonical value records its source, extraction method, record ID, confidence, and raw value in default-output provenance.

## Runtime Config Projection

The internal canonical record is always built first. A JSON config can then reshape the final output without modifying code.

Supported config behavior:

* select a subset of fields
* rename output fields with `path`
* remap from a canonical field with optional `from`
* omit `from` when `path` is already the canonical path
* apply per-field normalization such as `E164`, `canonical`, `email`, or `date`
* toggle confidence and provenance
* choose missing-value behavior: `null`, `omit`, or `error`
* validate selected output fields against their requested types

The included `samples/custom_config.json` demonstrates:

```text
full_name       → name
emails[0]       → primary_email
phones[0]       → primary_phone
skills[].name   → skills
years_experience uses its canonical path directly
```

## Requirements

* Python 3.11+

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run Default Canonical Output

```bash
python -m src.cli --csv samples/recruiter_export.csv --notes samples/recruiter_notes.txt --out outputs/default_output.json
```

This writes the complete canonical schema, including:

```text
candidate_id, full_name, emails, phones, location, links,
headline, years_experience, skills, experience, education,
provenance, overall_confidence
```

## Run Custom Configured Output

```bash
python -m src.cli --csv samples/recruiter_export.csv --notes samples/recruiter_notes.txt --config samples/custom_config.json --out outputs/custom_output.json
```

Example custom output:

```json
{
  "name": "Aditi Rao",
  "primary_email": "aditi.rao@example.com",
  "primary_phone": "+919876543210",
  "skills": [
    "FastAPI",
    "JavaScript",
    "Python",
    "Redis"
  ],
  "years_experience": 4.0,
  "overall_confidence": 0.86
}
```

## Robustness Behavior

* Missing or unreadable sources generate warnings and do not crash the run.
* Invalid emails, phones, and dates are omitted safely.
* Duplicate normalized values are deduplicated.
* Conflicting values remain traceable through provenance while the merge selects a deterministic winner.
* Same-name records without a matching email or phone are not merged automatically.

The included fixtures intentionally contain an invalid phone value, `12345`. The pipeline omits it and prints a warning while continuing to generate valid output.

## Tests

Run:

```bash
python -m pytest -q
```

The test suite verifies:

* valid Indian-phone normalization and invalid-phone rejection
* CSV and recruiter-note records merge into two canonical candidates
* skill alias normalization: `JS → JavaScript`
* custom projection returns `null` for Karan’s missing valid phone
* confidence appears while provenance remains excluded in the custom output

## Assumptions

The repository includes deterministic representative fixtures under `samples/` to demonstrate structured and unstructured source coverage, normalization, conflict resolution, runtime projection, and malformed-input handling.

## Scope and Extensibility

This implementation deliberately focuses on recruiter CSV and recruiter-note extractors to prioritize deterministic and explainable behavior.

Future adapters for GitHub, LinkedIn, resume parsing, PDF/DOCX extraction, or LLM-assisted extraction can emit into the same evidence layer without changing normalization, linking, merging, projection, or validation.
