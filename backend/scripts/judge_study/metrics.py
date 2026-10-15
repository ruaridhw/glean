"""The measures #124 asks for, as pure functions over scores."""

from __future__ import annotations

from dataclasses import dataclass

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


def _weighted_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Cohen's kappa with quadratic weights: a miss by 3 costs nine times a miss by 1."""
    n = len(pairs)
    observed = sum(_penalty(a, b) for a, b in pairs) / n
    first = [sum(a == level for a, _ in pairs) / n for level in range(1, LEVELS + 1)]
    second = [sum(b == level for _, b in pairs) / n for level in range(1, LEVELS + 1)]
    expected = sum(
        first[i - 1] * second[j - 1] * _penalty(i, j) for i in range(1, LEVELS + 1) for j in range(1, LEVELS + 1)
    )
    if expected == 0:
        return None
    return 1 - observed / expected


def _penalty(a: int, b: int) -> float:
    return (a - b) ** 2 / (LEVELS - 1) ** 2


def confusion_matrix(pairs: list[tuple[int, int]]) -> list[list[int]]:
    """`matrix[i][j]` counts outputs the first judge scored i+1 and the second j+1."""
    matrix = [[0] * LEVELS for _ in range(LEVELS)]
    for a, b in pairs:
        matrix[a - 1][b - 1] += 1
    return matrix
