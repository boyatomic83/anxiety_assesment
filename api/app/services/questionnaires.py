"""Load questionnaire definitions from app/questionnaires/*.json.

Validated wording is never stored in the JSON. Definitions reference text files that
scripts/fetch_questionnaires.py extracts from the official forms:

- item ``text_file``: one item per line, in the order the items reference that file
- ``options_file`` (questionnaire- or item-level): one label per line, in option order
- ``timeframe_file``: the instruction / timeframe paragraph
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas.questionnaire import QuestionnaireDef

QUESTIONNAIRE_DIR = Path(__file__).resolve().parent.parent / "questionnaires"


class QuestionnaireNotFound(KeyError):
    pass


class QuestionnaireDefinitionError(ValueError):
    pass


def _read_text_lines(base: Path, rel: str, where: str) -> list[str]:
    path = (base / rel).resolve()
    if not path.is_relative_to(base.resolve()):
        raise QuestionnaireDefinitionError(f"{where}: {rel} is outside {base}")
    if not path.is_file():
        raise QuestionnaireDefinitionError(
            f"{where}: {rel} not found (run scripts/fetch_questionnaires.py)"
        )
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _apply_labels(options: list[dict], labels: list[str], where: str, rel: str) -> list[dict]:
    if len(labels) != len(options):
        raise QuestionnaireDefinitionError(
            f"{where}: {rel} has {len(labels)} lines but {len(options)} options are defined"
        )
    return [{**opt, "label": label} for opt, label in zip(options, labels, strict=True)]


def resolve_definition(raw: dict[str, Any], base: Path) -> dict[str, Any]:
    """Return a copy of ``raw`` with every ``*_file`` reference replaced by its text."""
    q = json.loads(json.dumps(raw))  # deep copy
    qid = q.get("id", "?")

    if rel := q.pop("timeframe_file", None):
        q["timeframe"] = " ".join(_read_text_lines(base, rel, qid))

    if rel := q.pop("options_file", None):
        q["options"] = _apply_labels(
            q.get("options") or [], _read_text_lines(base, rel, qid), qid, rel
        )

    by_file: dict[str, list[dict]] = {}
    for item in q.get("items", []):
        if rel := item.pop("text_file", None):
            by_file.setdefault(rel, []).append(item)
        if rel := item.pop("options_file", None):
            where = f"{qid}.{item.get('id')}"
            item["options"] = _apply_labels(
                item.get("options") or [], _read_text_lines(base, rel, where), where, rel
            )
    for rel, items in by_file.items():
        lines = _read_text_lines(base, rel, qid)
        if len(lines) != len(items):
            raise QuestionnaireDefinitionError(
                f"{qid}: {rel} has {len(lines)} lines but {len(items)} items reference it"
            )
        for item, text in zip(items, lines, strict=True):
            item["text"] = text

    # Official validated translations: {"hi": {"text_file", "timeframe_file", "options_file"}}
    translations: dict[str, dict] = {}
    for lang, files in (q.get("i18n") or {}).items():
        where = f"{qid}.i18n.{lang}"
        tr: dict[str, Any] = {}
        if rel := files.get("text_file"):
            tr["items"] = _read_text_lines(base, rel, where)
            if len(tr["items"]) != len(q.get("items", [])):
                raise QuestionnaireDefinitionError(
                    f"{where}: {rel} has {len(tr['items'])} lines but there are "
                    f"{len(q.get('items', []))} items"
                )
        if rel := files.get("timeframe_file"):
            tr["timeframe"] = " ".join(_read_text_lines(base, rel, where))
        if rel := files.get("options_file"):
            tr["options"] = _read_text_lines(base, rel, where)
            if len(tr["options"]) != len(q.get("options") or []):
                raise QuestionnaireDefinitionError(f"{where}: {rel} option count mismatch")
        translations[lang] = tr
    q["i18n"] = translations
    return q


def load_dir(directory: Path) -> dict[str, QuestionnaireDef]:
    defs: dict[str, QuestionnaireDef] = {}
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        q = QuestionnaireDef.model_validate(resolve_definition(raw, directory))
        if q.id != path.stem:
            raise QuestionnaireDefinitionError(f"{path.name}: id '{q.id}' must match the file name")
        defs[q.id] = q
    return defs


@lru_cache
def load_all() -> dict[str, QuestionnaireDef]:
    return load_dir(QUESTIONNAIRE_DIR)


def get_questionnaire(questionnaire_id: str) -> QuestionnaireDef:
    try:
        return load_all()[questionnaire_id]
    except KeyError:
        raise QuestionnaireNotFound(questionnaire_id) from None
