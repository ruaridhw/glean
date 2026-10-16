from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.rubric_scale import rubric_score_question
from tests.integration.evals.judges import rubrics

ALL_RUBRICS = {
    "receipt scan": rubrics.RECEIPT_SCAN_RUBRIC,
    "meal plan": rubrics.MEAL_PLAN_RUBRIC,
    "recipe import": rubrics.RECIPE_IMPORT_RUBRIC,
    "pantry description": rubrics.PURCHASE_DESCRIPTION_RUBRIC,
    "shopping-list description": rubrics.SHOPPING_LIST_DESCRIPTION_RUBRIC,
}


class TestRubricScoreQuestion:
    @pytest.mark.parametrize("rubric", ALL_RUBRICS.values(), ids=ALL_RUBRICS.keys())
    def test_every_rubric_becomes_a_five_level_scale_from_worst_to_best(self, rubric: str) -> None:
        question = rubric_score_question(rubric)

        assert question.type == "score"
        assert len(question.criteria) == 5

    def test_levels_are_the_rubric_text_unchanged_and_ordered_lowest_first(self) -> None:
        question = rubric_score_question(rubrics.RECEIPT_SCAN_RUBRIC)

        assert question.criteria[0] == "Wrong (completely misidentified item)"
        assert question.criteria[4] == "Perfect canonical name, correct unit conversion, accurate price calculation"

    def test_a_level_keeps_its_own_dashes_and_punctuation(self) -> None:
        question = rubric_score_question(rubrics.MEAL_PLAN_RUBRIC)

        assert question.criteria[4].startswith("Excellent — uses expiring/urgent pantry items")

    def test_instructions_carry_the_rubric_framing_but_not_the_output_format_line(self) -> None:
        question = rubric_score_question(rubrics.RECIPE_IMPORT_RUBRIC)

        assert question.instructions.startswith("You are evaluating a recipe extraction system.")
        assert "Return structured data" not in question.instructions

    def test_a_rubric_without_five_levels_is_refused(self) -> None:
        with pytest.raises(ValueError, match="five levels"):
            rubric_score_question("Rate 1-5:\n\n5 = great\n1 = bad")
