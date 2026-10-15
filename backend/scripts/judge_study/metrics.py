"""The measures #124 asks for, as pure functions over scores."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from judge_study.results import OutputItem

LEVELS = 5


@dataclass(frozen=True)
class Agreement:
    n: int
    exact: float | None
    within_one: float | None
    kappa: float | None


def agreement(pairs: list[tuple[int, int]]) -> Agreement:
    if not pairs:
        return Agreement(0, None, None, None)
    n = len(pairs)
    return Agreement(
        n=n,
        exact=sum(a == b for a, b in pairs) / n,
        within_one=sum(abs(a - b) <= 1 for a, b in pairs) / n,
        kappa=_weighted_kappa(pairs),
    )


def _weighted_kappa(pairs: list[tuple[float, float]]) -> float | None:
    """Cohen's kappa with squared-distance weights: a miss by 3 costs nine times a miss by 1.

    Scores may be half points. The chance disagreement is the mean squared distance between every first-judge
    score and every second-judge score, which is what the marginal distributions imply.
    """
    n = len(pairs)
    observed = sum(_penalty(a, b) for a, b in pairs) / n
    expected = sum(_penalty(a, b) for a, _ in pairs for _, b in pairs) / (n * n)
    if expected == 0:
        return None
    return 1 - observed / expected


def _penalty(a: float, b: float) -> float:
    return (a - b) ** 2 / (LEVELS - 1) ** 2


def confusion_matrix(pairs: list[tuple[int, int]]) -> list[list[int]]:
    """`matrix[i][j]` counts outputs the first judge scored i+1 and the second j+1."""
    matrix = [[0] * LEVELS for _ in range(LEVELS)]
    for a, b in pairs:
        matrix[a - 1][b - 1] += 1
    return matrix


type Rater = Literal["llm", "decision", "human", "panel_claude", "panel_gpt"]


def item_score(item: OutputItem, rater: Rater) -> int | None:
    """One score per output: the human's, or the median of a judge's repeats."""
    if rater == "human":
        return item.human_score
    scores = sorted(j.score for j in item.judgements if j.judge == rater)
    return scores[(len(scores) - 1) // 2] if scores else None


def judge_pairs(items: list[OutputItem], first: Rater, second: Rater) -> list[tuple[int, int]]:
    pairs = [(item_score(item, first), item_score(item, second)) for item in items]
    return [(a, b) for a, b in pairs if a is not None and b is not None]


def disagreements(items: list[OutputItem]) -> list[OutputItem]:
    """Outputs the two judges score differently, the widest gap first."""
    gaps = []
    for item in items:
        llm, decision = item_score(item, "llm"), item_score(item, "decision")
        if llm is not None and decision is not None and llm != decision:
            gaps.append((abs(llm - decision), item))
    return [item for _, item in sorted(gaps, key=lambda gap: -gap[0])]


@dataclass(frozen=True)
class ReliabilityBin:
    """`accuracy` is the share of outputs whose decision-judge score equals the human's."""

    lower: float
    upper: float
    n: int
    mean_confidence: float
    accuracy: float


def reliability_bins(
    items: list[OutputItem], bins: int = 5, reference: Literal["human", "panel"] = "human"
) -> list[ReliabilityBin]:
    """Does the decision judge's confidence track whether it matches the reference? Empty bins are omitted.

    Against the panel, a match is equalling the panel mean, and contested outputs have no reference.
    """
    points: list[tuple[float, bool]] = []
    for item in items:
        confidences = [j.confidence for j in item.judgements if j.judge == "decision" and j.confidence is not None]
        score = item_score(item, "decision")
        if not confidences or score is None:
            continue
        if reference == "human":
            if item.human_score is not None:
                points.append((sum(confidences) / len(confidences), score == item.human_score))
        elif (panel_mean := panel_reference(item).score) is not None:
            points.append((sum(confidences) / len(confidences), score == panel_mean))
    result = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        inside = [(c, ok) for c, ok in points if lower <= c < upper or (index == bins - 1 and c == 1.0)]
        if inside:
            result.append(
                ReliabilityBin(
                    lower,
                    upper,
                    len(inside),
                    sum(c for c, _ in inside) / len(inside),
                    sum(ok for _, ok in inside) / len(inside),
                )
            )
    return result


@dataclass(frozen=True)
class Drift:
    items: int
    identical_share: float | None
    mean_range: float | None
    max_range: int | None


def drift(items: list[OutputItem], judge: Literal["llm", "decision"]) -> Drift:
    """How much one judge's repeated scores of the same output differ. Outputs scored once can't drift."""
    ranges = []
    for item in items:
        scores = [j.score for j in item.judgements if j.judge == judge]
        if len(scores) >= 2:
            ranges.append(max(scores) - min(scores))
    if not ranges:
        return Drift(0, None, None, None)
    return Drift(len(ranges), sum(r == 0 for r in ranges) / len(ranges), sum(ranges) / len(ranges), max(ranges))


@dataclass(frozen=True)
class CostSummary:
    judgements: int
    total: float
    mean: float | None
    unreported: int


def cost_summary(items: list[OutputItem], judge: Literal["llm", "decision"]) -> CostSummary:
    judgements = [j for item in items for j in item.judgements if j.judge == judge]
    costs = [j.cost_usd for j in judgements if j.cost_usd is not None]
    return CostSummary(
        judgements=len(judgements),
        total=sum(costs),
        mean=sum(costs) / len(costs) if costs else None,
        unreported=len(judgements) - len(costs),
    )


@dataclass(frozen=True)
class Latency:
    p50: float | None
    p95: float | None


def latency_summary(items: list[OutputItem], judge: Literal["llm", "decision"]) -> Latency:
    seconds = sorted(j.latency_s for item in items for j in item.judgements if j.judge == judge)
    return Latency(_percentile(seconds, 50), _percentile(seconds, 95))


def _percentile(sorted_values: list[float], percent: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * percent / 100
    below = int(position)
    above = min(below + 1, len(sorted_values) - 1)
    return sorted_values[below] + (sorted_values[above] - sorted_values[below]) * (position - below)


@dataclass(frozen=True)
class PanelReference:
    """What the two strong judges agree an output deserves. `contested` means they differ by two or more."""

    score: float | None
    contested: bool


def panel_reference(item: OutputItem) -> PanelReference:
    first, second = item_score(item, "panel_claude"), item_score(item, "panel_gpt")
    if first is None or second is None:
        return PanelReference(None, False)
    if abs(first - second) >= 2:
        return PanelReference(None, True)
    mean = (first + second) / 2
    return PanelReference(int(mean) if mean == int(mean) else mean, False)


def agreement_with_panel(items: list[OutputItem], candidate: Literal["llm", "decision"]) -> Agreement:
    """A candidate judge against the panel mean, leaving out contested outputs.

    Exact means equal to the mean, so a candidate can never be exact on a half-point reference. Within one means
    no more than a point from the mean. Kappa uses the half-point references as they are.
    """
    pairs = candidate_reference_pairs(items, candidate)
    if not pairs:
        return Agreement(0, None, None, None)
    n = len(pairs)
    return Agreement(
        n=n,
        exact=sum(score == reference for score, reference in pairs) / n,
        within_one=sum(abs(score - reference) <= 1 for score, reference in pairs) / n,
        kappa=_weighted_kappa(pairs),
    )


def candidate_reference_pairs(
    items: list[OutputItem], candidate: Literal["llm", "decision"]
) -> list[tuple[int, float]]:
    pairs = []
    for item in items:
        reference, score = panel_reference(item).score, item_score(item, candidate)
        if reference is not None and score is not None:
            pairs.append((score, reference))
    return pairs


def reference_matrix(pairs: list[tuple[int, float]]) -> list[list[int]]:
    """`matrix[i][j]` counts outputs a candidate scored i+1 whose reference was 1 + j/2 (half points allowed)."""
    matrix = [[0] * (2 * LEVELS - 1) for _ in range(LEVELS)]
    for score, reference in pairs:
        matrix[score - 1][round((reference - 1) * 2)] += 1
    return matrix
