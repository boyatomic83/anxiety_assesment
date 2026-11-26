"""Builders for synthetic questionnaire definitions (placeholder text, never real items)."""

import json
from pathlib import Path

from app.schemas.questionnaire import QuestionnaireDef
from app.services.questionnaires import load_dir


def raw_def(**overrides) -> dict:
    d = {
        "id": "test",
        "name": "Test",
        "version": "1.0",
        "timeframe_file": "items/test_instructions.txt",
        "options": [{"value": 0, "label": "No"}, {"value": 1, "label": "Yes"}],
        "items": [
            {"id": "t_1", "text_file": "items/test.txt"},
            {"id": "t_2", "text_file": "items/test.txt"},
        ],
        "scoring": {"method": "sum"},
        "bands": [
            {"min": 0, "max": 0, "label": "Low", "level": 0},
            {"min": 1, "max": 2, "label": "High", "level": 1},
        ],
        "safety_items": [],
        "source": "synthetic",
        "licence": "test",
    }
    d.update(overrides)
    return d


def write_dir(tmp: Path, definition: dict, files: dict[str, str] | None = None) -> Path:
    (tmp / "items").mkdir(exist_ok=True)
    defaults = {
        "items/test.txt": "placeholder one\nplaceholder two\n",
        "items/test_instructions.txt": "placeholder instructions\n",
    }
    for rel, content in {**defaults, **(files or {})}.items():
        (tmp / rel).write_text(content, encoding="utf-8")
    (tmp / f"{definition['id']}.json").write_text(json.dumps(definition), encoding="utf-8")
    return tmp


def write_def(tmp: Path, method: str = "sum", bands: list | None = None) -> QuestionnaireDef:
    d = raw_def(scoring={"method": method})
    if bands is not None:
        d["bands"] = [{"min": a, "max": b, "label": lab, "level": lv} for a, b, lab, lv in bands]
    return load_dir(write_dir(tmp, d))["test"]
