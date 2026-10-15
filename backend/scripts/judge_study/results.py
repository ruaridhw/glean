"""The results file: frozen outputs, every judgement and the maintainer's scores, as JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path

type FeatureName = Literal[
    "receipt_scan", "meal_plan", "recipe_import", "pantry_description", "shopping_list_description"
]
type JudgeName = Literal["llm", "decision"]

SCORE_FIELD = Field(ge=1, le=5, description="Integer rubric score from 1 (bad) to 5 (perfect).")


class Judgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: JudgeName = Field(description="`llm` is today's eval judge; `decision` is the decision model's `score`.")
    repeat: int = Field(ge=1, description="Which of the repeated runs of this judge produced this judgement.")
    score: int = SCORE_FIELD
    model: str = Field(description="Model id, or the dated snapshot for the decision model.")
    latency_s: float = Field(ge=0, description="Wall-clock seconds for the call.")
    cost_usd: float | None = Field(default=None, description="Cost reported by OpenRouter; None if it wasn't reported.")
    weighted_score: float | None = Field(
        default=None, description="Decision judge only: probability-weighted position on the 1-5 scale."
    )
    confidence: float | None = Field(default=None, ge=0, le=1, description="Decision judge only: its own confidence.")
    probabilities: list[float] | None = Field(
        default=None, description="Decision judge only: probability of each level, 1 first."
    )


class OutputItem(BaseModel):
    """One frozen output of a feature's production prompt, which every judge scores."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(description="Stable id: `<feature>/<fixture example>/<output index>`.")
    feature: FeatureName
    input: dict[str, Any] = Field(description="What the feature was given, for display.")
    output: dict[str, Any] = Field(description="What the production prompt produced, for display.")
    judge_inputs: dict[str, Any] = Field(description="Arguments of the feature's judge prompt builder.")
    origin: Literal["production", "stress"] = Field(
        default="production",
        description="`stress` marks a deliberately degraded copy of a production output, added to widen the spread.",
    )
    judgements: list[Judgement] = Field(default_factory=list)
    human_score: int | None = Field(default=None, ge=1, le=5, description="The maintainer's score, if they gave one.")


class Results(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: dict[str, str] = Field(description="Which model produced outputs and served each judge.")
    items: list[OutputItem]

    def save(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> Results:
        return cls.model_validate_json(path.read_text())

    def with_human_scores(self, scores: dict[str, int]) -> Results:
        known = {item.item_id for item in self.items}
        for item_id in scores:
            if item_id not in known:
                raise KeyError(item_id)
        return self.model_copy(
            update={"items": [item.model_copy(update={"human_score": scores.get(item.item_id)}) for item in self.items]}
        )
