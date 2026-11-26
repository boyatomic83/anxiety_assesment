from fastapi import APIRouter, HTTPException, Query

from app.schemas.api import HelplinesOut
from app.services.questionnaires import QuestionnaireNotFound, get_questionnaire, load_all
from app.services.safety import helplines_for

router = APIRouter(tags=["questionnaires"])


@router.get("/questionnaires")
def list_questionnaires() -> list[dict]:
    return [
        {
            "id": q.id,
            "name": q.name,
            "version": q.version,
            "items": len(q.items),
            "languages": ["en", *sorted(q.i18n)],
        }
        for q in load_all().values()
    ]


@router.get("/questionnaires/{questionnaire_id}")
def questionnaire_detail(questionnaire_id: str, lang: str = Query("en", pattern="^[a-z]{2}$")):
    try:
        q = get_questionnaire(questionnaire_id)
    except QuestionnaireNotFound:
        raise HTTPException(404, "Questionnaire not found") from None
    data = q.model_dump(exclude={"i18n"})
    tr = q.i18n.get(lang)
    if tr:  # official validated translation only (see scripts/fetch_questionnaires.py)
        data["timeframe"] = tr.get("timeframe", data["timeframe"])
        for item, text in zip(data["items"], tr.get("items", []), strict=False):
            item["text"] = text
        if tr.get("options") and data.get("options"):
            for opt, label in zip(data["options"], tr["options"], strict=False):
                opt["label"] = label
        data["language"] = lang
    else:
        data["language"] = "en"
    return data


@router.get("/helplines", response_model=HelplinesOut)
def helplines(country: str | None = Query(None, min_length=2, max_length=2)):
    return helplines_for(country)
