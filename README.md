# Eightfold Candidate Profile Transformer

A deterministic Python CLI that combines structured recruiter CSV data and unstructured recruiter notes into clean, canonical candidate profiles.

The pipeline is evidence-first: extractors create source-attributed evidence, then normalization, identity linking, deterministic merge, configurable projection, and validation produce final JSON.

## Features

* Handles two source types:

  * **Structured:** recruiter CSV export
  * **Unstructured:** recruiter notes (`.txt`)
* Normalizes:

  * emails to lowercase
  * phones to E.164 when valid and country context is known
  * dates to `YYYY-MM`
  * locations such as `Bangalore → Bengaluru`
  * skill aliases such as `JS → JavaScript`
* Links records by normalized **email → phone → unambiguous full name**
* Resolves conflicts deterministically:

  * highest confidence
  * source priority: `recruiter_csv > recruiter_notes`
  * stable input order
* Preserves field-level provenance and confidence in canonical output
* Supports runtime config for field selection, renaming, normalization, confidence/provenance toggles, and missing-value policy
* Handles malformed input safely with warnings instead of crashing

## Project Structure

```text
eightfold-candidate-transformer/
├── src/
│   ├── cli.py            # CLI orchestration
│   ├── models.py         # Pydantic models and runtime config schema
│   ├── extractors.py     # CSV and recruiter-note extractors
│   ├── normalizers.py    # Email, phone, date, skill, location normalization
│   ├── linker.py         # Identity linking
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

## Pipeline

```text
CSV + Notes
→ Evidence Extraction
→ Field Normalization
→ Identity Linking
→ Trust-Based Merge + Confidence
→ Config Projection
→ Validation
→ JSON Output
```

## Requirements

* Python 3.11+
* Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the Default Canonical Output

```bash
python -m src.cli --csv samples/recruiter_export.csv --notes samples/recruiter_notes.txt --out outputs/default_output.json
```

This writes the complete canonical schema, including fields such as:

```text
candidate_id, full_name, emails, phones, location, links,
years_experience, skills, experience, education,
provenance, overall_confidence
```

## Run a Custom Configured Output

```bash
python -m src.cli --csv samples/recruiter_export.csv --notes samples/recruiter_notes.txt --config samples/custom_config.json --out outputs/custom_output.json
```

The included custom config demonstrates:

* `full_name → name`
* `emails[0] → primary_email`
* `phones[0] → primary_phone`
* `skills[].name → skills`
* confidence enabled
* provenance disabled
* missing values emitted as `null`

## Example Custom Output

```json
{
  "name": "Aditi Rao",
  "primary_email": "aditi.rao@example.com",
  "primary_phone": "+919876543210",
  "skills": ["FastAPI", "JavaScript", "Python", "Redis"],
  "years_experience": 4.0,
  "overall_confidence": 0.86
}
```

## Merge and Confidence Policy

For scalar fields, the winner is chosen by:

```text
highest confidence → source priority → stable input order
```

Source priority:

```text
recruiter_csv > recruiter_notes
```

Confidence defaults:

```text
Exact CSV field:                 0.90
Labeled / regex note extraction: 0.65
Conservative heuristic:          0.50
```

List fields such as emails, phones, skills, and experience retain valid normalized unique values. Each accepted value includes source and extraction-method provenance in the default output.

## Robustness Behavior

* Missing or unreadable sources generate warnings and do not crash the run.
* Invalid emails, phones, and dates are omitted instead of guessed.
* Duplicate aliases are normalized and deduplicated.
* Conflicting values remain traceable through provenance while a deterministic winner is selected.
* Same-name records without matching identifiers are not automatically merged.

For example, the sample phone value `12345` is invalid, so it is omitted and reported as a warning while processing continues.

## Tests

Run:

```bash
python -m pytest -q
```

The test suite verifies:

* valid Indian phone normalization and invalid-phone rejection
* merging CSV and note records into two canonical candidates
* canonical skill normalization (`JS → JavaScript`)
* runtime custom projection with a missing phone becoming `null`

## Scope

The current implementation intentionally focuses on recruiter CSV and recruiter-note sources to prioritize deterministic, explainable behavior.

Future source adapters such as GitHub, LinkedIn, resume parsing, PDF/DOCX extraction, or LLM-assisted extraction can feed the same evidence layer without changing normalization, linking, merging, projection, or validation.
