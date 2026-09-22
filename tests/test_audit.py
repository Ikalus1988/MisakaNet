from datetime import datetime, timezone

from intake_audit.audit import Intake, find_matches, referenced_intakes, render_markdown


def test_source_and_nested_provenance_are_detected(tmp_path):
    course = tmp_path / "course.md"
    course.write_text("""---\ntitle: A course\nsource: https://github.com/acme/repo/issues/1472\nprovenance:\n  issue: '#1635'\n---\nMention #999 in body only.\n""", encoding="utf-8")
    assert referenced_intakes(course.read_text()) == {1472, 1635}


def test_unrelated_body_or_numeric_fields_are_not_false_positives(tmp_path):
    course = tmp_path / "course.md"
    course.write_text("""---\ntitle: A course\nid: 1472\n---\nsource: #1472\n""", encoding="utf-8")
    assert referenced_intakes(course.read_text()) == set()


def test_only_open_referenced_intakes_are_reported(tmp_path):
    course = tmp_path / "course.md"
    course.write_text("---\nsource: '#1472'\n---\n", encoding="utf-8")
    intakes = [
        Intake(1472, datetime(2026, 9, 20, tzinfo=timezone.utc)),
        Intake(9999, datetime(2026, 9, 1, tzinfo=timezone.utc)),
    ]
    matches = find_matches(intakes, tmp_path)
    assert [(m.intake.number, m.course_path) for m in matches] == [(1472, str(course))]
    assert "#1472" in render_markdown(matches)
    assert "#9999" not in render_markdown(matches)


def test_removing_reference_makes_check_empty_and_adding_it_reproduces(tmp_path):
    course = tmp_path / "course.md"
    intake = Intake(1472, datetime(2026, 9, 20, tzinfo=timezone.utc))
    course.write_text("---\ntitle: A course\n---\n", encoding="utf-8")
    assert find_matches([intake], tmp_path) == []
    course.write_text("---\nprovenance:\n  issue: '#1472'\n---\n", encoding="utf-8")
    assert len(find_matches([intake], tmp_path)) == 1

