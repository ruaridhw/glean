"""Read-only evaluation of a decision model against labelled dietary samples.

Scores a model's per-flag probabilities against sample labels at the calibrated reference cutoffs
and reports the confusion, so a substitution can be measured before anything decides a meal. It holds
no corpus store and writes nothing: the answers it reads are the only thing it touches, and a
candidate agreeing with the reference at these cutoffs is a comparison, not a calibration.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from glean.decisions import DecisionError, Usage
from glean.meal_plan.dietary_decisions import (
    CALIBRATED_DIETARY,
    DIETARY_FLAGS,
    DietaryCalibration,
    dietary_questions,
)
from glean.observability import logger

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from glean.decisions import DecisionClient

_REFERENCE = (
    "Reference only: these cutoffs were measured on the calibrated model. Agreeing with them at these "
    "numbers is not a calibration of this model, and no result here permits it to decide a meal."
)
_REMAINING_VALIDATION = (
    "A production substitution still needs its own cutoffs measured over the whole labelled corpus, a run "
    "that reaches 100% assessment coverage, and one reviewed calibration change. A sample this size cannot "
    "certify an allergy flag."
)


class EvaluationInputError(Exception):
    """The samples can't evaluate anything: none given, none labelling an asked flag, or a misspelt flag."""


class LabelledSample(BaseModel):
    """One recipe with the flags it does or doesn't break, labelled independently of any model."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    ingredients: list[str]
    violates: dict[str, bool] = Field(description="Flag name to whether the recipe breaks it.")


def load_labelled_samples(paths: Iterable[Path]) -> list[LabelledSample]:
    """Read labelled samples from fixture files shaped `{"rows": [...]}`."""
    return [LabelledSample.model_validate(row) for path in paths for row in json.loads(path.read_text())["rows"]]


@dataclass(frozen=True, slots=True)
class SampleScore:
    """One model answer, its label, and whether the reference cutoff would exclude the recipe."""

    sample_id: str
    flag: str
    violates: bool
    probability: float
    threshold: float
    excluded: bool


@dataclass(frozen=True, slots=True)
class FlagSummary:
    """What one flag's answers did at the reference cutoff."""

    flag: str
    threshold: float
    violations: int
    clean: int
    missed: tuple[SampleScore, ...]
    wrongly_excluded: tuple[SampleScore, ...]
    lowest_violation: float | None
    highest_clean: float | None

    @property
    def evaluated(self) -> bool:
        """Whether any sample labelled this flag: an unlabelled flag proves nothing either way."""
        return self.violations + self.clean > 0


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """A candidate model's answers over labelled samples. Says nothing about its eligibility."""

    requested_model: str
    served_models: Mapping[str, int]
    samples: int
    """How many samples were answered; `failures` counts the ones that were not."""
    scores: tuple[SampleScore, ...]
    failures: tuple[str, ...]
    usage: Usage
    flags: tuple[str, ...]
    calibration: DietaryCalibration

    def evidence(self) -> dict[str, Any]:
        """Everything the run saw, as JSON: every label and probability, not only the mistakes.

        Saved evidence can be re-scored at other cutoffs later without asking the model again.
        """
        return {
            "requested_model": self.requested_model,
            "served_models": dict(self.served_models),
            "samples_scored": self.samples,
            "requests_failed": len(self.failures),
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "cost": self.usage.cost,
            },
            "reference_calibration": {
                "model": {"request": self.calibration.model.request, "served": list(self.calibration.model.served)},
                "thresholds": dict(self.calibration.thresholds),
                "default_threshold": self.calibration.default_threshold,
                "evidence": self.calibration.evidence,
            },
            "failures": list(self.failures),
            "scores": [
                {
                    "sample_id": score.sample_id,
                    "flag": score.flag,
                    "violates": score.violates,
                    "probability": score.probability,
                    "threshold": score.threshold,
                    "excluded": score.excluded,
                }
                for score in self.scores
            ],
        }

    @property
    def evaluated_flags(self) -> tuple[str, ...]:
        return tuple(flag for flag, summary in self.summaries().items() if summary.evaluated)

    def summaries(self) -> dict[str, FlagSummary]:
        return {
            flag: _summarise(flag, [score for score in self.scores if score.flag == flag], self.calibration)
            for flag in self.flags
        }

    def render(self) -> str:
        lines = [
            f"Requested model: {self.requested_model}",
            f"Served identities: {_counts(self.served_models) or 'none'}",
            f"Samples scored: {self.samples}, requests failed: {len(self.failures)}",
            f"Usage: {self.usage.input_tokens} in / {self.usage.output_tokens} out, ${self.usage.cost:.6f}",
        ]
        for flag, summary in self.summaries().items():
            lines.append("")
            if not summary.evaluated:
                lines.append(f"{flag}: NOT EVALUATED (no labelled samples)")
                continue
            lines.append(
                f"{flag}: {summary.violations} labelled violations, {summary.clean} clean, "
                f"at the {summary.threshold:g} reference cutoff"
            )
            lines.append(f"  missed: {_scores(summary.missed) or 'none'}")
            lines.append(f"  excluded though clean: {_scores(summary.wrongly_excluded) or 'none'}")
            lines.append(
                f"  lowest labelled violation {_probability(summary.lowest_violation)}, "
                f"highest clean {_probability(summary.highest_clean)}"
            )
        if self.failures:
            lines.append("")
            lines.append("Failures:")
            lines.extend(f"  {failure}" for failure in self.failures)
        lines.append("")
        lines.append(_REFERENCE)
        lines.append(_REMAINING_VALIDATION)
        return "\n".join(lines)


def evaluate_dietary_model(
    client: DecisionClient,
    samples: Iterable[LabelledSample],
    *,
    calibration: DietaryCalibration = CALIBRATED_DIETARY,
    flags: tuple[str, ...] = DIETARY_FLAGS,
) -> EvaluationReport:
    """Ask `client` every dietary question about each sample and score it against the labels.

    A request that fails is reported and skipped; the rest are still scored. The calibration only
    supplies the reference cutoffs, so a model it does not cover can be measured safely.
    """
    samples = list(samples)
    _check_labelled(samples, flags)
    questions = dietary_questions(flags)
    scores: list[SampleScore] = []
    failures: list[str] = []
    served: Counter[str] = Counter()
    usage = Usage(input_tokens=0, output_tokens=0, cost=0.0)
    count = 0
    for sample in samples:
        count += 1
        state = {"recipe_title": sample.title, "ingredients": sample.ingredients}
        try:
            decision = client.decide(state, questions)
        except DecisionError as exc:
            failures.append(f"{sample.id}: {exc}")
            logger.warning("dietary evaluation request failed", extra={"sample_id": sample.id, "error": str(exc)})
            continue
        served[decision.model] += 1
        usage = usage.model_copy(
            update={
                "input_tokens": usage.input_tokens + decision.usage.input_tokens,
                "output_tokens": usage.output_tokens + decision.usage.output_tokens,
                "cost": usage.cost + decision.usage.cost,
            }
        )
        for flag in flags:
            violates = sample.violates.get(flag)
            if violates is None:
                continue
            probability = decision.noul(flag).noul
            threshold = calibration.threshold_for(flag)
            scores.append(
                SampleScore(
                    sample_id=sample.id,
                    flag=flag,
                    violates=violates,
                    probability=probability,
                    threshold=threshold,
                    excluded=probability >= threshold,
                )
            )
    return EvaluationReport(
        requested_model=client.model.request,
        served_models=dict(served),
        samples=count - len(failures),
        scores=tuple(scores),
        failures=tuple(failures),
        usage=usage,
        flags=flags,
        calibration=calibration,
    )


def _check_labelled(samples: list[LabelledSample], flags: tuple[str, ...]) -> None:
    """Refuse input that would read as a clean run: no samples, a misspelt flag, or nothing being asked about."""
    if not samples:
        raise EvaluationInputError("No labelled samples to evaluate")
    unknown = sorted({flag for sample in samples for flag in sample.violates} - set(DIETARY_FLAGS))
    if unknown:
        raise EvaluationInputError(f"Labels for flags the decision model is not asked about (misspelt?): {unknown}")
    if not any(flag in sample.violates for sample in samples for flag in flags):
        raise EvaluationInputError(
            f"The samples label none of the flags being evaluated ({', '.join(flags)}): nothing was measured"
        )


def _summarise(flag: str, scores: list[SampleScore], calibration: DietaryCalibration) -> FlagSummary:
    violations = [score for score in scores if score.violates]
    clean = [score for score in scores if not score.violates]
    return FlagSummary(
        flag=flag,
        threshold=calibration.threshold_for(flag),
        violations=len(violations),
        clean=len(clean),
        missed=tuple(score for score in violations if not score.excluded),
        wrongly_excluded=tuple(score for score in clean if score.excluded),
        lowest_violation=min((score.probability for score in violations), default=None),
        highest_clean=max((score.probability for score in clean), default=None),
    )


def _scores(scores: tuple[SampleScore, ...]) -> str:
    return ", ".join(f"{score.sample_id}={score.probability:.3f}" for score in scores)


def _probability(value: float | None) -> str:
    return "none" if value is None else f"{value:.3f}"


def _counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{name} x{count}" for name, count in sorted(counts.items()))
