"""V5's two enrichers: the five attributes and the active-time bucket, and the bars they accept at.

Seams: the declared questions (names, options, wording-bearing types), the acceptance rule as a plain
function of a parsed `Decision`, the state each family contributes to one request, and one end-to-end run
through the runner. No HTTP here: the acceptance rule is a pure function of the decision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glean.decisions import DECISION_MODEL, ChoiceAnswer, Decision, ScoreAnswer, Usage
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.attributes import (
    ACTIVE_TIME_QUESTION,
    ActiveTimeBucket,
    Cuisine,
    DishType,
    MainCarb,
    MainProtein,
    WholeFood,
)
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.enrichment import (
    ACTIVE_TIME_ENRICHER,
    ATTRIBUTE_ENRICHER,
    DIETARY_ENRICHER,
    EnrichmentError,
    SafeSide,
    run_enrichment,
)
from glean.recipes.enrichment.active_time import active_time_question
from glean.recipes.enrichment.attributes import WHOLE_FOOD_LEVELS, AttributeEnricher, attribute_questions
from glean.recipes.enrichment.enricher import MIN_ATTRIBUTE_BAR, attribute_bar
from glean.recipes.stored import StoredIngredient, StoredInstruction, StoredRecipe
from tests.recipes.enrichment.fakes import FakeDecisionApi

if TYPE_CHECKING:
    from pathlib import Path


def test_the_attribute_enricher_asks_the_five_g1_attributes() -> None:
    questions = ATTRIBUTE_ENRICHER.questions()

    assert [question.name for question in questions] == [
        "attribute:main_protein",
        "attribute:main_carb",
        "attribute:dish_type",
        "attribute:cuisine",
        "attribute:whole_food",
    ]


@pytest.mark.parametrize(
    ("attribute", "values"),
    [
        ("main_protein", MainProtein),
        ("main_carb", MainCarb),
        ("dish_type", DishType),
        ("cuisine", Cuisine),
    ],
)
def test_each_choice_offers_exactly_the_settled_values_and_never_unsure(attribute, values) -> None:
    question = attribute_questions()[attribute].question

    assert question.type == "choice"
    assert list(question.criteria) == [value.value for value in values if value.value != "unsure"]


def test_whole_food_is_a_score_with_its_levels_lowest_first() -> None:
    question = attribute_questions()["whole_food"].question

    assert question.type == "score"
    assert len(question.criteria) == 3
    assert [level.value for level in WHOLE_FOOD_LEVELS] == ["processed", "mixed", "whole"]


def test_every_attribute_question_starts_at_the_settled_bar_and_leans_to_the_high_side() -> None:
    for question in ATTRIBUTE_ENRICHER.questions():
        assert (question.bar.threshold, question.bar.safe_side) == (0.8, SafeSide.HIGH)


def test_a_bar_is_tunable_per_attribute_and_only_for_that_attribute() -> None:
    questions = attribute_questions(bars={"cuisine": 0.75})

    assert questions["cuisine"].bar.threshold == 0.75
    assert questions["main_protein"].bar.threshold == 0.8


@pytest.mark.parametrize("threshold", [0.69, 0.5, 0.0, 1.01])
def test_a_bar_looser_than_g1_allows_is_refused(threshold: float) -> None:
    with pytest.raises(ValueError, match=r"between 0\.7 and 1\.0"):
        attribute_bar(threshold)


def test_the_floor_is_the_one_g1_settled() -> None:
    assert MIN_ATTRIBUTE_BAR == 0.7


def test_an_attribute_at_or_above_its_bar_stores_the_top_option() -> None:
    answer = attribute_questions()["main_protein"].accept(
        _decision(_choice("attribute:main_protein", "chicken", {"chicken": 0.8, "beef": 0.2}))
    )

    assert (answer.probability, answer.value) == (0.8, "chicken")


def test_an_attribute_below_its_bar_stores_unsure_with_the_probability_that_failed_it() -> None:
    answer = attribute_questions()["main_protein"].accept(
        _decision(_choice("attribute:main_protein", "chicken", {"chicken": 0.79, "beef": 0.21}))
    )

    assert (answer.probability, answer.value) == (0.79, "unsure")


def test_a_tuned_bar_moves_the_line_for_that_attribute() -> None:
    decision = _decision(_choice("attribute:cuisine", "thai", {"thai": 0.76, "italian": 0.24}))

    assert attribute_questions()["cuisine"].accept(decision).value == "unsure"
    assert attribute_questions(bars={"cuisine": 0.75})["cuisine"].accept(decision).value == "thai"


def test_whole_food_accepts_the_level_with_the_highest_probability() -> None:
    answer = attribute_questions()["whole_food"].accept(
        _decision(_score("attribute:whole_food", {0: 0.05, 1: 0.15, 2: 0.8}))
    )

    assert (answer.probability, answer.value) == (0.8, "whole")


def test_whole_food_below_its_bar_is_unsure_rather_than_a_guess() -> None:
    answer = attribute_questions()["whole_food"].accept(
        _decision(_score("attribute:whole_food", {0: 0.1, 1: 0.6, 2: 0.3}))
    )

    assert (answer.probability, answer.value) == (0.6, "unsure")


def test_the_active_time_enricher_asks_one_bucketed_score() -> None:
    questions = ACTIVE_TIME_ENRICHER.questions()

    assert [question.name for question in questions] == [ACTIVE_TIME_QUESTION]
    question = questions[0]
    assert question.question.type == "score"
    assert question.question.criteria[0].startswith("Up to 15 minutes")
    assert len(question.question.criteria) == 5
    assert (question.bar.threshold, question.bar.safe_side) == (0.8, SafeSide.HIGH)


@pytest.mark.parametrize(
    ("level", "bucket"),
    [
        (0, ActiveTimeBucket.UP_TO_15),
        (1, ActiveTimeBucket.FROM_15_TO_30),
        (2, ActiveTimeBucket.FROM_30_TO_45),
        (3, ActiveTimeBucket.FROM_45_TO_60),
        (4, ActiveTimeBucket.OVER_60),
    ],
)
def test_each_active_time_level_is_the_bucket_it_sits_at(level: int, bucket: ActiveTimeBucket) -> None:
    probabilities = dict.fromkeys(range(5), 0.01)
    probabilities[level] = 0.96

    answer = active_time_question().accept(_decision(_score(ACTIVE_TIME_QUESTION, probabilities)))

    assert answer.value == bucket.value


def test_active_time_below_its_bar_falls_back_to_unsure_which_the_filter_reads_as_total_time() -> None:
    answer = active_time_question().accept(
        _decision(_score(ACTIVE_TIME_QUESTION, {0: 0.1, 1: 0.45, 2: 0.3, 3: 0.1, 4: 0.05}))
    )

    assert (answer.probability, answer.value) == (0.45, "unsure")


def test_the_active_time_bar_is_tunable_but_not_below_the_floor() -> None:
    assert active_time_question(0.75).bar.threshold == 0.75

    with pytest.raises(ValueError, match=r"between 0\.7 and 1\.0"):
        active_time_question(0.6)


def test_a_dietary_run_sends_no_method_and_no_times_but_an_attribute_run_does(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    dietary = FakeDecisionApi()
    attributes = FakeDecisionApi()

    run_enrichment(corpus, dietary.client(), enrichers=(DIETARY_ENRICHER,))
    run_enrichment(corpus, attributes.client(), enrichers=(ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER))

    assert set(dietary.requests[0]["state"]) == {"recipe_title", "ingredients"}
    state = attributes.requests[0]["state"]
    assert state["method"] == ["Chop the vegetables.", "Simmer until soft."]
    assert (state["prep_time_mins"], state["total_time_mins"]) == (10, 40)


def test_one_request_per_recipe_carries_dietary_attributes_and_active_time_together(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi()

    report = run_enrichment(corpus, api.client())

    assert len(api.requests) == 1  # not one request per family
    assert set(api.requests[0]["questions"]) == {
        *(question.name for question in DIETARY_ENRICHER.questions()),
        *(question.name for question in ATTRIBUTE_ENRICHER.questions()),
        ACTIVE_TIME_QUESTION,
    }
    assert report.coverage == 1.0


def test_a_full_run_stores_a_label_or_an_unsure_for_every_attribute_and_a_bucket_for_time(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    # The fake answers 0.9 at the top option, so every question clears its 0.8 bar.
    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER))

    stored = {answer.question: answer for answer in corpus.answers()}

    assert stored["attribute:main_protein"].value == MainProtein.CHICKEN.value
    assert stored["attribute:whole_food"].value == WholeFood.WHOLE.value
    assert stored[ACTIVE_TIME_QUESTION].value == ActiveTimeBucket.OVER_60.value


def test_a_question_below_its_bar_is_reported_as_unsure_not_as_labelled(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)

    # The fake answers 0.9 at its top option; a 0.95 bar for one attribute stores `unsure` for it alone.
    report = run_enrichment(
        corpus,
        FakeDecisionApi().client(),
        enrichers=(AttributeEnricher(bars={"main_protein": 0.95}),),
    )

    coverage = report.question("attribute:main_protein")
    assert (coverage.current, coverage.unsure, coverage.labelled) == (1, 1, 0)
    assert report.question("attribute:cuisine").labelled == 1
    assert "Labelled answers: 4/5 current; 1 stored unsure" in report.render()


def test_the_same_run_is_asked_nothing_the_second_time(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    run_enrichment(corpus, FakeDecisionApi().client())
    second = FakeDecisionApi()

    report = run_enrichment(corpus, second.client())

    assert second.requests == []
    assert report.coverage == 1.0


def test_two_enrichers_may_not_claim_one_question(tmp_path: Path) -> None:
    with pytest.raises(EnrichmentError, match="more than one enricher"):
        run_enrichment(
            _corpus(tmp_path), FakeDecisionApi().client(), enrichers=(ATTRIBUTE_ENRICHER, ATTRIBUTE_ENRICHER)
        )


def _decision(*answers: dict) -> Decision:
    return Decision(
        id="gen-dec-test",
        model=DECISION_MODEL,
        provider="test",
        answers={name: answer for part in answers for name, answer in part.items()},
        usage=Usage(input_tokens=0, output_tokens=0, cost=0.0),
    )


def _choice(name: str, top: str, probabilities: dict[str, float]) -> dict:
    return {name: ChoiceAnswer(type="choice", choice=top, probabilities=probabilities, confidence=probabilities[top])}


def _score(name: str, probabilities: dict[int, float]) -> dict:
    top = max(probabilities, key=lambda index: probabilities[index])
    return {
        name: ScoreAnswer(
            type="score",
            score=sum(index * probability for index, probability in probabilities.items()),
            probabilities=probabilities,
            confidence=probabilities[top],
        )
    }


def _corpus(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(BlobCorpusBackend(FilesystemBlobStore(tmp_path)))
    corpus.save(
        StoredRecipe(
            external_id="rec_synthetic",
            title="Synthetic Traybake",
            prep_time_mins=10,
            total_time_mins=40,
            # The fake reads this marker as "answer high", so the questions all clear their bars.
            ingredients=[StoredIngredient(canonical_name="basil pesto", quantity=1, unit="each")],
            instructions=[
                StoredInstruction(step_number=1, phase="main", text="Chop the vegetables."),
                StoredInstruction(step_number=2, phase="main", text="Simmer until soft."),
            ],
        )
    )
    return corpus
