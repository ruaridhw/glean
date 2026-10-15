from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.metrics import agreement, confusion_matrix


class TestAgreement:
    def test_exact_and_within_one_are_shares_of_the_pairs(self) -> None:
        result = agreement([(4, 4), (4, 5), (2, 4), (3, 3)])

        assert result.n == 4
        assert result.exact == 0.5
        assert result.within_one == 0.75

    def test_weighted_kappa_is_one_when_the_judges_agree_on_a_varied_set(self) -> None:
        assert agreement([(1, 1), (3, 3), (5, 5), (2, 2)]).kappa == pytest.approx(1.0)

    def test_weighted_kappa_is_zero_when_agreement_is_no_better_than_chance(self) -> None:
        assert agreement([(1, 1), (5, 5), (1, 5), (5, 1)]).kappa == pytest.approx(0.0)

    def test_weighted_kappa_penalises_a_far_miss_more_than_a_near_miss(self) -> None:
        assert agreement([(1, 1), (2, 2), (3, 3), (4, 4), (5, 4)]).kappa == pytest.approx(0.9411764705882353)
        assert agreement([(1, 1), (2, 2), (3, 3), (4, 4), (5, 1)]).kappa < 0.5

    def test_kappa_is_undefined_when_one_judge_never_varies(self) -> None:
        # Every output scored 4 by both: there is no spread to agree about, so no chance-corrected figure exists.
        assert agreement([(4, 4), (4, 4), (4, 4)]).kappa is None

    def test_no_pairs_gives_no_figures_rather_than_an_error(self) -> None:
        result = agreement([])

        assert (result.n, result.exact, result.within_one, result.kappa) == (0, None, None, None)


class TestConfusionMatrix:
    def test_rows_are_the_first_judges_score_and_columns_the_seconds(self) -> None:
        matrix = confusion_matrix([(5, 4), (5, 4), (4, 4), (1, 3)])

        assert matrix[4][3] == 2  # first judge said 5, second said 4
        assert matrix[3][3] == 1
        assert matrix[0][2] == 1
        assert sum(map(sum, matrix)) == 4

    def test_it_always_covers_all_five_levels(self) -> None:
        matrix = confusion_matrix([])

        assert len(matrix) == 5
        assert all(len(row) == 5 for row in matrix)
