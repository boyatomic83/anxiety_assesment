"""Pydantic schema for questionnaire JSON definitions (SPEC.md section 4).

Loading a definition validates it fully, so adding a questionnaire needs no code changes:
drop a JSON file in app/questionnaires/ and the tests check it automatically.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Option(_Strict):
    value: int
    label: str


class Item(_Strict):
    id: str
    text: str
    # Per-item options (e.g. OASIS). Falls back to the questionnaire-level options.
    options: list[Option] | None = None


class Band(_Strict):
    min: int
    max: int
    label: str
    level: int = Field(ge=0)


class Subscale(_Strict):
    name: str
    items: list[str] = Field(min_length=1)
    multiplier: int = Field(default=1, ge=1)
    bands: list[Band] = Field(min_length=1)


class Scoring(_Strict):
    method: Literal["sum", "sum_x2", "subscales"]
    subscales: dict[str, Subscale] | None = None


class SafetyItem(_Strict):
    item_id: str
    min_value: int = Field(ge=1, description="Flag when the answer is >= this value")


class QuestionnaireDef(_Strict):
    id: str
    name: str
    version: str
    timeframe: str
    instructions: str | None = None
    options: list[Option] | None = None
    items: list[Item] = Field(min_length=1)
    scoring: Scoring
    bands: list[Band] = Field(default_factory=list)
    safety_items: list[SafetyItem] = Field(default_factory=list)
    source: str
    licence: str
    notes: str | None = None
    i18n: dict[str, dict] = Field(default_factory=dict)

    def options_for(self, item: Item) -> list[Option]:
        opts = item.options or self.options
        if opts is None:  # pragma: no cover - prevented by _validate
            raise ValueError(f"item {item.id} has no options")
        return opts

    @property
    def item_ids(self) -> list[str]:
        return [i.id for i in self.items]

    def _range(self, item_ids: list[str], multiplier: int) -> tuple[int, int]:
        by_id = {i.id: i for i in self.items}
        lo = sum(min(o.value for o in self.options_for(by_id[i])) for i in item_ids)
        hi = sum(max(o.value for o in self.options_for(by_id[i])) for i in item_ids)
        return lo * multiplier, hi * multiplier

    @model_validator(mode="after")
    def _validate(self) -> Self:
        ids = self.item_ids
        if len(ids) != len(set(ids)):
            raise ValueError("item ids must be unique")
        for item in self.items:
            opts = item.options or self.options
            if not opts:
                raise ValueError(f"item {item.id} has no options")
            values = [o.value for o in opts]
            if len(values) != len(set(values)):
                raise ValueError(f"item {item.id} has duplicate option values")
        for s in self.safety_items:
            if s.item_id not in ids:
                raise ValueError(f"safety item {s.item_id} is not an item")

        if self.scoring.method == "subscales":
            if not self.scoring.subscales:
                raise ValueError("method 'subscales' needs scoring.subscales")
            if self.bands:
                raise ValueError("subscale questionnaires band per subscale, not at the top")
            for key, sub in self.scoring.subscales.items():
                unknown = set(sub.items) - set(ids)
                if unknown:
                    raise ValueError(f"subscale {key} has unknown items {sorted(unknown)}")
                _check_bands(f"subscale {key}", sub.bands, *self._range(sub.items, sub.multiplier))
        else:
            if self.scoring.subscales:
                raise ValueError(f"method '{self.scoring.method}' does not take subscales")
            mult = 2 if self.scoring.method == "sum_x2" else 1
            _check_bands(self.id, self.bands, *self._range(ids, mult))
        return self


def _check_bands(where: str, bands: list[Band], lo: int, hi: int) -> None:
    """Bands must be sorted, contiguous, and cover exactly [lo, hi]."""
    if not bands:
        raise ValueError(f"{where}: bands are required")
    expected = lo
    for b in bands:
        if b.min != expected or b.max < b.min:
            raise ValueError(f"{where}: bands must be contiguous from {lo} (problem at {b.label})")
        expected = b.max + 1
    if bands[-1].max != hi:
        raise ValueError(f"{where}: bands must end at the maximum score {hi}")
