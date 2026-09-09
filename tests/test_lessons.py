import datetime
from app.lessons import RawLesson, normalize, map_status, clean_subject


def test_map_status():
    assert map_status(None) == "normal"
    assert map_status("cancelled") == "cancelled"
    assert map_status("irregular") == "substitution"


def test_clean_subject_strips_markers():
    assert clean_subject("ATH11#") == "ATH11"
    assert clean_subject("DBA8=") == "DBA8"
    assert clean_subject("SWD") == "SWD"


def _raw(h, m, subject, room, teacher, code=None):
    d = datetime.datetime(2026, 9, 10, h, m)
    return RawLesson(start=d, end=d + datetime.timedelta(minutes=45),
                     subject=subject, room=room, teacher=teacher, code=code)


def test_team_teaching_merges_teachers():
    raw = [
        _raw(11, 15, "SWD", "K104", "VS"),
        _raw(11, 15, "SWD", "K104", "KP"),
    ]
    result = normalize(raw)
    assert len(result) == 1
    assert result[0].teacher == "KP, VS"  # alphabetisch, dedupliziert
    assert result[0].subject == "SWD"


def test_normalize_maps_fields_and_status():
    raw = [_raw(17, 0, "ATH11#", "K003", "GS", code="cancelled")]
    (lesson,) = normalize(raw)
    assert lesson.date == datetime.date(2026, 9, 10)
    assert lesson.start_time == datetime.time(17, 0)
    assert lesson.end_time == datetime.time(17, 45)
    assert lesson.subject == "ATH11"
    assert lesson.status == "cancelled"


def test_normalize_sorted_by_start():
    raw = [_raw(10, 0, "B", "r", "t"), _raw(8, 0, "A", "r", "t")]
    result = normalize(raw)
    assert [l.subject for l in result] == ["A", "B"]
