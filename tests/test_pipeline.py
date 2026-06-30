from src.extractors import extract_csv_records, extract_note_records
from src.linker import link_records
from src.merger import merge_groups
from src.normalizers import normalize_phone, normalize_source_record
from src.projector import load_runtime_config, project_candidates


CSV_PATH = "samples/recruiter_export.csv"
NOTES_PATH = "samples/recruiter_notes.txt"
CONFIG_PATH = "samples/custom_config.json"


def build_candidates():
    csv_records, _ = extract_csv_records(CSV_PATH)
    note_records, _ = extract_note_records(NOTES_PATH)

    normalized_records = [
        normalize_source_record(record)
        for record in csv_records + note_records
    ]

    return merge_groups(link_records(normalized_records))


def test_phone_normalization_and_invalid_phone():
    assert normalize_phone("98765 43210", "IN") == "+919876543210"
    assert normalize_phone("12345", "IN") is None


def test_sources_merge_into_two_candidates():
    candidates = build_candidates()

    assert len(candidates) == 2

    aditi = next(
        candidate
        for candidate in candidates
        if candidate.full_name == "Aditi Rao"
    )

    assert aditi.emails == ["aditi.rao@example.com"]
    assert aditi.phones == ["+919876543210"]
    assert aditi.years_experience == 4.0
    assert aditi.location.city == "Bengaluru"

    skill_names = [skill.name for skill in aditi.skills]
    assert "JavaScript" in skill_names
    assert "JS" not in skill_names


def test_custom_projection_handles_missing_phone():
    candidates = build_candidates()
    config = load_runtime_config(CONFIG_PATH)

    output = project_candidates(candidates, config)

    karan = next(
        candidate
        for candidate in output
        if candidate["name"] == "Karan Mehta"
    )

    assert karan["primary_phone"] is None
    assert "provenance" not in karan
    assert "overall_confidence" in karan