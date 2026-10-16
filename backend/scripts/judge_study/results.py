"""The results file: frozen outputs, every judgement and the maintainer's scores, as JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path

type FeatureName = Literal[
    "receipt_scan", "meal_plan", "recipe_import", "pantry_description", "shopping_list_description"
]
type JudgeName = Literal["llm", "decision", "panel_claude", "panel_gpt"]
type CostBasis = Literal["reported", "estimated"]

COST_BASIS_FIELD = Field(
    default=None,
    description=(
        "`reported` is a cost the decisions endpoint reported; `estimated` is reported tokens times OpenRouter's "
        "list price, used for chat models because OpenRouter's generation stats don't list these calls."
    ),
)

SCORE_FIELD = Field(ge=1, le=5, description="Integer rubric score from 1 (bad) to 5 (perfect).")


class Judgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    judge: JudgeName = Field(
        description=(
            "`llm` is today's eval judge; `decision` is the decision model's `score`; "
            "`panel_*` are the strong reference judges."
        )
    )
    repeat: int = Field(ge=1, description="Which of the repeated runs of this judge produced this judgement.")
    score: int = SCORE_FIELD
    model: str = Field(description="Model id, or the dated snapshot for the decision model.")
    latency_s: float = Field(
        ge=0, description="Wall-clock seconds from the first attempt to the answer: the sum of its attempts' times."
    )
    cost_usd: float | None = Field(
        default=None,
        description=(
            "Known cost over every attempt at this judgement, earlier runs' and failed ones included. See `cost_basis` "
            "for whether it is reported or estimated, and `unpriced_attempts` for how many calls it leaves out. "
            "None when no attempt could be priced."
        ),
    )
    cost_basis: CostBasis | None = COST_BASIS_FIELD
    unpriced_attempts: int = Field(
        default=0,
        ge=0,
        description="Attempts at this judgement whose cost is unknown. When above 0, `cost_usd` is only a lower bound.",
    )
    attempts: int = Field(default=1, ge=1, description="Calls it took to obtain this judgement; failed calls are paid.")
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
    feature: FeatureName = Field(description="Which of the five LLM features produced this output.")
    input: dict[str, Any] = Field(description="What the feature was given, for display.")
    output: dict[str, Any] = Field(description="What the production prompt produced, for display.")
    judge_inputs: dict[str, Any] = Field(description="Arguments of the feature's judge prompt builder.")
    origin: Literal["production", "stress"] = Field(
        default="production",
        description="`stress` marks a deliberately degraded copy of a production output, added to widen the spread.",
    )
    judgements: list[Judgement] = Field(
        default_factory=list, description="Every judgement obtained for this output, from every judge and repeat."
    )
    human_score: int | None = Field(default=None, ge=1, le=5, description="The maintainer's score, if they gave one.")


class Attempt(BaseModel):
    """One paid (or attempted) call to a judge, kept whether it worked or not."""

    model_config = ConfigDict(extra="forbid")

    judge: JudgeName = Field(description="Which judge was called.")
    item_id: str = Field(description="The output being judged.")
    repeat: int = Field(ge=1, description="Which repeat of the judge this call was for.")
    attempt: int = Field(ge=1, description="1 for the first call at this judgement, 2 for the retry.")
    outcome: Literal["ok", "parse_failure", "call_failure"] = Field(
        description="`parse_failure`: the judge answered but not usably. `call_failure`: no answer (timeout, HTTP)."
    )
    latency_s: float = Field(ge=0, description="Wall-clock seconds the call took, failed or not.")
    input_tokens: int | None = Field(default=None, description="Input tokens reported; None if the call reported none.")
    output_tokens: int | None = Field(default=None, description="Output tokens reported; None if none were reported.")
    cost_usd: float | None = Field(
        default=None, description="Cost of this call; None when it couldn't be priced, never a made-up zero."
    )
    cost_basis: CostBasis | None = COST_BASIS_FIELD
    error: str | None = Field(default=None, description="Exception type and the start of its message, if it failed.")


class Failure(BaseModel):
    """A judgement that could not be obtained after every attempt, kept so reliability can be reported."""

    model_config = ConfigDict(extra="forbid")

    judge: JudgeName = Field(description="The judge that never produced a usable score.")
    item_id: str = Field(description="The output it was judging.")
    repeat: int = Field(ge=1, description="The repeat that could not be obtained.")
    error: str = Field(description="Exception type and the start of its message.")


class Results(BaseModel):
    model_config = ConfigDict(extra="forbid")

    models: dict[str, str] = Field(description="Which model produced outputs and served each judge.")
    items: list[OutputItem] = Field(description="Every frozen output, with the judgements obtained for it.")
    failures: list[Failure] = Field(
        default_factory=list, description="Judgements that could not be obtained after every attempt."
    )
    attempts: list[Attempt] = Field(
        default_factory=list, description="Every call made to the candidate judges since attempts were first logged."
    )

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
