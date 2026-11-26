"""Scoring tests: known score -> band examples for every questionnaire (ids/values only)."""

import pytest

from app.services.questionnaires import get_questionnaire
from app.services.scoring import InvalidAnswers, score


def answers_for(qid: str, values: list[int]) -> dict[str, int]:
    q = get_questionnaire(qid)
    assert len(values) == len(q.items)
    return dict(zip(q.item_ids, values, strict=True))


def spread(total: int, n: int, max_value: int) -> list[int]:
    """n answers in 0..max_value summing to total (fills from the front)."""
    out = []
    for _ in range(n):
        v = min(max_value, total)
        out.append(v)
        total -= v
    assert total == 0
    return out


# (questionnaire, total, expected band, expected level) -- every band boundary
SUM_CASES = [
    ("gad2", 0, "Negative screen", 0),
    ("gad2", 2, "Negative screen", 0),
    ("gad2", 3, "Positive screen", 1),
    ("gad2", 6, "Positive screen", 1),
    ("gad7", 0, "Minimal", 0),
    ("gad7", 4, "Minimal", 0),
    ("gad7", 5, "Mild", 1),
    ("gad7", 9, "Mild", 1),
    ("gad7", 10, "Moderate", 2),
    ("gad7", 14, "Moderate", 2),
    ("gad7", 15, "Severe", 3),
    ("gad7", 21, "Severe", 3),
    ("phq9", 0, "Minimal", 0),
    ("phq9", 4, "Minimal", 0),
    ("phq9", 5, "Mild", 1),
    ("phq9", 9, "Mild", 1),
    ("phq9", 10, "Moderate", 2),
    ("phq9", 14, "Moderate", 2),
    ("phq9", 15, "Moderately severe", 3),
    ("phq9", 19, "Moderately severe", 3),
    ("phq9", 20, "Severe", 4),
    ("phq9", 27, "Severe", 4),
    ("oasis", 0, "Below clinical cut-off", 0),
    ("oasis", 7, "Below clinical cut-off", 0),
    ("oasis", 8, "Above clinical cut-off", 1),
    ("oasis", 20, "Above clinical cut-off", 1),
]


@pytest.mark.parametrize(("qid", "total", "band", "level"), SUM_CASES)
def test_sum_scoring_bands(qid, total, band, level):
    q = get_questionnaire(qid)
    max_value = max(o.value for o in q.options_for(q.items[0]))
    result = score(q, answers_for(qid, spread(total, len(q.items), max_value)))
    assert (result.total, result.band, result.level) == (total, band, level)
    assert result.subscales == {}
    assert result.questionnaire_id == qid
    assert result.questionnaire_version == q.version


def test_gad7_worked_example():
    # 1+2+0+3+1+2+1 = 10 -> Moderate
    r = score(get_questionnaire("gad7"), answers_for("gad7", [1, 2, 0, 3, 1, 2, 1]))
    assert (r.total, r.band, r.level) == (10, "Moderate", 2)


def test_phq9_worked_example():
    # 2+2+1+1+0+1+2+1+0 = 10 -> Moderate
    r = score(get_questionnaire("phq9"), answers_for("phq9", [2, 2, 1, 1, 0, 1, 2, 1, 0]))
    assert (r.total, r.band, r.level) == (10, "Moderate", 2)


def test_gad2_uses_gad7_item_ids():
    gad2, gad7 = get_questionnaire("gad2"), get_questionnaire("gad7")
    assert gad2.item_ids == gad7.item_ids[:2]


DASS_SUBSCALES = {
    "depression": [3, 5, 10, 13, 16, 17, 21],
    "anxiety": [2, 4, 7, 9, 15, 19, 20],
    "stress": [1, 6, 8, 11, 12, 14, 18],
}

# (subscale, doubled score, band, level) -- every DASS-21 band boundary
DASS_CASES = [
    ("depression", 0, "Normal", 0),
    ("depression", 8, "Normal", 0),
    ("depression", 10, "Mild", 1),
    ("depression", 12, "Mild", 1),
    ("depression", 14, "Moderate", 2),
    ("depression", 20, "Moderate", 2),
    ("depression", 22, "Severe", 3),
    ("depression", 26, "Severe", 3),
    ("depression", 28, "Extremely severe", 4),
    ("depression", 42, "Extremely severe", 4),
    ("anxiety", 0, "Normal", 0),
    ("anxiety", 6, "Normal", 0),
    ("anxiety", 8, "Mild", 1),
    ("anxiety", 10, "Moderate", 2),
    ("anxiety", 14, "Moderate", 2),
    ("anxiety", 16, "Severe", 3),
    ("anxiety", 18, "Severe", 3),
    ("anxiety", 20, "Extremely severe", 4),
    ("anxiety", 42, "Extremely severe", 4),
    ("stress", 0, "Normal", 0),
    ("stress", 14, "Normal", 0),
    ("stress", 16, "Mild", 1),
    ("stress", 18, "Mild", 1),
    ("stress", 20, "Moderate", 2),
    ("stress", 24, "Moderate", 2),
    ("stress", 26, "Severe", 3),
    ("stress", 32, "Severe", 3),
    ("stress", 34, "Extremely severe", 4),
    ("stress", 42, "Extremely severe", 4),
]


@pytest.mark.parametrize(("sub", "doubled", "band", "level"), DASS_CASES)
def test_dass21_subscale_bands(sub, doubled, band, level):
    q = get_questionnaire("dass21")
    answers = {i: 0 for i in q.item_ids}
    for item_no, v in zip(DASS_SUBSCALES[sub], spread(doubled // 2, 7, 3), strict=True):
        answers[f"dass21_{item_no}"] = v
    r = score(q, answers)
    assert r.subscales[sub].model_dump() == {"score": doubled, "band": band, "level": level}
    others = set(DASS_SUBSCALES) - {sub}
    assert all(r.subscales[o].score == 0 for o in others)
    assert r.total == doubled
    assert r.band is None and r.level is None


def test_dass21_subscales_partition_all_items():
    q = get_questionnaire("dass21")
    assert q.scoring.subscales is not None
    for key, sub in q.scoring.subscales.items():
        assert sub.items == [f"dass21_{n}" for n in DASS_SUBSCALES[key]]
        assert sub.multiplier == 2
    all_items = [i for s in q.scoring.subscales.values() for i in s.items]
    assert sorted(all_items) == sorted(q.item_ids)


def test_dass21_mixed_example():
    q = get_questionnaire("dass21")
    answers = {i: 1 for i in q.item_ids}  # every item "1" -> 7 * 1 * 2 = 14 per subscale
    r = score(q, answers)
    assert r.subscales["depression"].band == "Moderate"  # 14
    assert r.subscales["anxiety"].band == "Moderate"  # 14
    assert r.subscales["stress"].band == "Normal"  # 14
    assert r.total == 42


def test_scoring_is_deterministic():
    q = get_questionnaire("phq9")
    a = answers_for("phq9", [3, 0, 1, 2, 3, 0, 1, 2, 3])
    assert score(q, a) == score(q, a)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda a: a.pop("gad7_3"), "missing"),
        (lambda a: a.update(gad7_99=1), "unknown"),
        (lambda a: a.update(gad7_1=4), "not one of"),
        (lambda a: a.update(gad7_1=-1), "not one of"),
        (lambda a: a.update(gad7_1=True), "integer"),
        (lambda a: a.update(gad7_1="2"), "integer"),
        (lambda a: a.update(gad7_1=1.0), "integer"),
    ],
)
def test_invalid_answers_rejected(change, message):
    a = answers_for("gad7", [0] * 7)
    change(a)
    with pytest.raises(InvalidAnswers, match=message):
        score(get_questionnaire("gad7"), a)


def test_oasis_uses_per_item_options():
    q = get_questionnaire("oasis")
    a = answers_for("oasis", [4, 4, 4, 4, 4])
    assert score(q, a).total == 20
    a["oasis_1"] = 5
    with pytest.raises(InvalidAnswers):
        score(q, a)


def test_sum_x2_method(tmp_path):
    from tests.helpers import write_def

    q = write_def(tmp_path, method="sum_x2", bands=[[0, 1, "Low", 0], [2, 4, "High", 1]])
    r = score(q, {"t_1": 1, "t_2": 0})
    assert (r.total, r.band) == (2, "High")


def test_band_gap_is_reported():
    from app.services.scoring import _band_for

    with pytest.raises(InvalidAnswers, match="outside every band"):
        _band_for(99, get_questionnaire("gad7").bands)
