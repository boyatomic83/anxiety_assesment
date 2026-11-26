"""Request/response schemas for the public API (SPEC.md section 7)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

AgeBand = Literal["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
Gender = Literal["female", "male", "non_binary", "other", "prefer_not"]
Duration = Literal["<2w", "2w-1m", "1-6m", "6m+"]
Role = Literal["user", "clinician", "admin"]


class ContextIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    age_band: AgeBand | None = None
    gender: Gender | None = None
    language: Literal["en", "hi"] | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    symptom_duration: Duration | None = None
    caffeine_cups: int | None = Field(default=None, ge=0, le=30)
    stressful_event: bool | None = None
    free_text: str | None = Field(default=None, max_length=2000)


class SessionCreate(BaseModel):
    consent: Literal[True]
    consent_version: str
    locale: Literal["en", "hi"] = "en"
    context: ContextIn | None = None


class SessionCreated(BaseModel):
    id: uuid.UUID
    guest_token: str | None
    consent_version: str
    expires_at: datetime | None


class AnswersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questionnaire_id: str
    answers: dict[str, int]
    item_timings: dict[str, float] = Field(default_factory=dict)


class AnswersSaved(BaseModel):
    questionnaire_id: str
    saved_items: int
    complete: bool


class Helpline(BaseModel):
    name: str
    number: str | None = None
    alt_number: str | None = None
    url: str | None = None


class HelplinesOut(BaseModel):
    country: str
    helplines: list[Helpline]


class TopFactor(BaseModel):
    feature: str
    label: str
    impact: float


class MLEstimate(BaseModel):
    label: Literal["AI-assisted estimate"] = "AI-assisted estimate"
    composite_severity: int
    composite_label: str
    probabilities: dict[str, float]
    confidence: float
    top_factors: list[TopFactor]
    model_version: str
    agrees_with_validated: bool | None


class ResponseQuality(BaseModel):
    ok: bool
    flags: list[str]


class ResultOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    created_at: datetime
    flagged: bool
    crisis: HelplinesOut | None
    primary: Literal["validated"] = "validated"
    scores: dict[str, dict]
    ml: MLEstimate | None
    response_quality: ResponseQuality | None
    disclaimer: str


class HistoryItem(BaseModel):
    result_id: uuid.UUID
    created_at: datetime
    flagged: bool
    scores: dict[str, dict]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    locale: Literal["en", "hi"] = "en"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: Role
    locale: str
    reminder_days: int | None


class SettingsIn(BaseModel):
    locale: Literal["en", "hi"] | None = None
    reminder_days: Literal[7, 14, 30, 90] | None = None
    clear_reminder: bool = False


class ClaimIn(BaseModel):
    session_id: uuid.UUID
    guest_token: str


class ShareOut(BaseModel):
    code: str
    expires_at: datetime


class RedeemIn(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class PatientResult(BaseModel):
    result_id: uuid.UUID
    patient_ref: str
    created_at: datetime
    flagged: bool
    scores: dict[str, dict]
    ml_composite: str | None


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target: str | None
    created_at: datetime


class RoleIn(BaseModel):
    email: EmailStr
    role: Role


DISCLAIMER = (
    "Calma is a screening tool, not a diagnosis. These results can't replace an assessment "
    "by a qualified health professional."
)
