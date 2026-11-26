"""Definition + loader tests. Never print or compare validated wording; check structure only."""

import json

import pytest
from pydantic import ValidationError

from app.schemas.questionnaire import QuestionnaireDef
from app.services.questionnaires import (
    QUESTIONNAIRE_DIR,
    QuestionnaireDefinitionError,
    QuestionnaireNotFound,
    get_questionnaire,
    load_all,
    load_dir,
    resolve_definition,
)
from tests.helpers import raw_def, write_dir

EXPECTED = {"gad2": 2, "gad7": 7, "phq9": 9, "oasis": 5, "dass21": 21}


def test_all_v1_questionnaires_load():
    defs = load_all()
    assert {k: len(v.items) for k, v in defs.items()} == EXPECTED


@pytest.mark.parametrize("qid", sorted(EXPECTED))
def test_every_item_and_option_has_text(qid):
    q = get_questionnaire(qid)
    assert q.timeframe.strip()
    for item in q.items:
        assert item.text.strip(), f"{item.id} has no text"
        assert all(o.label.strip() for o in q.options_for(item))


def test_definitions_keep_wording_out_of_json():
    """JSON holds structure only; validated wording lives in items/*.txt."""
    for path in QUESTIONNAIRE_DIR.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert "timeframe" not in raw
        assert all("text" not in item and "text_file" in item for item in raw["items"])


def test_phq9_item_9_is_a_safety_item():
    q = get_questionnaire("phq9")
    assert [(s.item_id, s.min_value) for s in q.safety_items] == [("phq9_9", 1)]


def test_option_values():
    assert [o.value for o in get_questionnaire("gad7").options or []] == [0, 1, 2, 3]
    assert [o.value for o in get_questionnaire("dass21").options or []] == [0, 1, 2, 3]
    oasis = get_questionnaire("oasis")
    assert all([o.value for o in oasis.options_for(i)] == [0, 1, 2, 3, 4] for i in oasis.items)


def test_unknown_questionnaire():
    with pytest.raises(QuestionnaireNotFound):
        get_questionnaire("nope")


# ---------- loader errors ----------


def test_line_count_mismatch_is_a_clear_error(tmp_path):
    write_dir(tmp_path, raw_def(), {"items/test.txt": "only one line\n"})
    with pytest.raises(QuestionnaireDefinitionError, match="has 1 lines but 2 items"):
        load_dir(tmp_path)


def test_missing_text_file(tmp_path):
    d = raw_def()
    d["items"][0]["text_file"] = d["items"][1]["text_file"] = "items/missing.txt"
    write_dir(tmp_path, d)
    with pytest.raises(QuestionnaireDefinitionError, match="not found"):
        load_dir(tmp_path)


def test_text_file_outside_questionnaire_dir(tmp_path):
    (tmp_path / "secret.txt").write_text("x\n")
    (tmp_path / "q").mkdir()
    write_dir(tmp_path / "q", raw_def(timeframe_file="../secret.txt"))
    with pytest.raises(QuestionnaireDefinitionError, match="outside"):
        load_dir(tmp_path / "q")


def test_options_file_count_mismatch(tmp_path):
    d = raw_def(options=[{"value": 0}, {"value": 1}], options_file="items/opts.txt")
    write_dir(tmp_path, d, {"items/opts.txt": "a\n"})
    with pytest.raises(QuestionnaireDefinitionError, match="1 lines but 2 options"):
        load_dir(tmp_path)


def test_item_options_file(tmp_path):
    d = raw_def()
    del d["options"]
    for n, item in enumerate(d["items"]):
        item["options"] = [{"value": 0}, {"value": 1}]
        item["options_file"] = f"items/o{n}.txt"
    q = load_dir(write_dir(tmp_path, d, {"items/o0.txt": "a\nb\n", "items/o1.txt": "c\nd\n"}))
    assert [o.label for o in q["test"].options_for(q["test"].items[1])] == ["c", "d"]


def test_id_must_match_file_name(tmp_path):
    write_dir(tmp_path, raw_def())
    (tmp_path / "test.json").rename(tmp_path / "other.json")
    with pytest.raises(QuestionnaireDefinitionError, match="must match the file name"):
        load_dir(tmp_path)


def test_resolve_does_not_mutate_input(tmp_path):
    d = raw_def()
    write_dir(tmp_path, d)
    before = json.dumps(d, sort_keys=True)
    resolve_definition(d, tmp_path)
    assert json.dumps(d, sort_keys=True) == before


# ---------- schema validation ----------


def resolved(**overrides) -> dict:
    d = raw_def(**overrides)
    d.pop("timeframe_file")
    d["timeframe"] = "t"
    for n, item in enumerate(d["items"]):
        item.pop("text_file")
        item["text"] = f"placeholder {n}"
    return d


def band(a, b, level=0):
    return {"min": a, "max": b, "label": f"{a}-{b}", "level": level}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"bands": [band(0, 0), band(2, 2)]}, "contiguous"),
        ({"bands": [band(1, 2)]}, "contiguous"),
        ({"bands": [band(0, 1)]}, "end at the maximum"),
        ({"bands": [band(0, 1), band(2, 1)]}, "contiguous"),
        ({"bands": []}, "bands are required"),
        ({"safety_items": [{"item_id": "zz", "min_value": 1}]}, "safety item"),
        ({"options": None}, "has no options"),
        ({"options": [{"value": 0, "label": "a"}, {"value": 0, "label": "b"}]}, "duplicate"),
        ({"scoring": {"method": "subscales"}}, "needs scoring.subscales"),
        (
            {
                "scoring": {
                    "method": "sum",
                    "subscales": {"x": {"name": "x", "items": ["t_1"], "bands": [band(0, 1)]}},
                }
            },
            "does not take subscales",
        ),
    ],
)
def test_invalid_definitions(overrides, message):
    with pytest.raises(ValidationError, match=message):
        QuestionnaireDef.model_validate(resolved(**overrides))


def test_duplicate_item_ids():
    d = resolved()
    d["items"][1]["id"] = "t_1"
    with pytest.raises(ValidationError, match="unique"):
        QuestionnaireDef.model_validate(d)


def _subscale_def(items, bands, top_bands=None):
    return resolved(
        scoring={
            "method": "subscales",
            "subscales": {"s": {"name": "S", "items": items, "multiplier": 2, "bands": bands}},
        },
        bands=top_bands or [],
    )


def test_subscale_validation():
    ok = QuestionnaireDef.model_validate(_subscale_def(["t_1", "t_2"], [band(0, 4)]))
    assert ok.scoring.subscales is not None
    with pytest.raises(ValidationError, match="unknown items"):
        QuestionnaireDef.model_validate(_subscale_def(["t_9"], [band(0, 2)]))
    with pytest.raises(ValidationError, match="end at the maximum"):
        QuestionnaireDef.model_validate(_subscale_def(["t_1", "t_2"], [band(0, 2)]))
    with pytest.raises(ValidationError, match="per subscale"):
        QuestionnaireDef.model_validate(_subscale_def(["t_1"], [band(0, 2)], [band(0, 2)]))


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        QuestionnaireDef.model_validate(resolved(typo_field=1))


# ---------- official translations ----------


def test_translation_files_are_loaded(tmp_path):
    d = raw_def(
        i18n={
            "hi": {
                "text_file": "items/hi.txt",
                "timeframe_file": "items/hi_t.txt",
                "options_file": "items/hi_o.txt",
            }
        }
    )
    files = {
        "items/hi.txt": "अनुवाद एक\nअनुवाद दो\n",
        "items/hi_t.txt": "समय\n",
        "items/hi_o.txt": "नहीं\nहाँ\n",
    }
    q = load_dir(write_dir(tmp_path, d, files))["test"]
    assert q.i18n["hi"]["items"] == ["अनुवाद एक", "अनुवाद दो"]
    assert q.i18n["hi"]["timeframe"] == "समय"
    assert q.i18n["hi"]["options"] == ["नहीं", "हाँ"]


@pytest.mark.parametrize(
    ("files", "message"),
    [
        ({"items/hi.txt": "only one\n"}, "1 lines but there are 2 items"),
        ({"items/hi.txt": "a\nb\n", "items/hi_o.txt": "x\n"}, "option count mismatch"),
    ],
)
def test_translation_mismatches(tmp_path, files, message):
    d = raw_def(i18n={"hi": {"text_file": "items/hi.txt", "options_file": "items/hi_o.txt"}})
    files.setdefault("items/hi_o.txt", "x\ny\n")
    with pytest.raises(QuestionnaireDefinitionError, match=message):
        load_dir(write_dir(tmp_path, d, files))


def test_api_serves_translation_when_available(client, monkeypatch):
    from app.services import questionnaires as qs

    q = qs.get_questionnaire("gad2")
    fake = q.model_copy(
        update={
            "i18n": {
                "hi": {
                    "items": ["अनुवाद 1", "अनुवाद 2"],
                    "timeframe": "समय",
                    "options": ["क", "ख", "ग", "घ"],
                }
            }
        }
    )
    monkeypatch.setitem(qs.load_all(), "gad2", fake)
    hi = client.get("/api/v1/questionnaires/gad2?lang=hi").json()
    assert hi["language"] == "hi" and hi["items"][0]["text"] == "अनुवाद 1"
    assert hi["timeframe"] == "समय" and hi["options"][3]["label"] == "घ"
    en = client.get("/api/v1/questionnaires/gad7?lang=hi").json()
    assert en["language"] == "en"  # no official Hindi version yet -> English
