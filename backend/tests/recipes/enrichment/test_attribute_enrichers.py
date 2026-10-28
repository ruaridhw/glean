"""V5's two enrichers: the five attributes and the active-time bucket, and the bars they accept at.

Seams: the declared questions (names, options, wording-bearing types), the acceptance rule as a plain
function of a parsed `Decision`, the state each family contributes to one request, and one end-to-end run
through the runner. No HTTP here: the acceptance rule is a pure function of the decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from glean.decisions import DECISION_MODEL, ChoiceAnswer, Decision, DecisionModel, ScoreAnswer, Usage
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.answers import RecipeAnswer, content_fingerprint
from glean.recipes.attributes import (
    ACTIVE_TIME_QUESTION,
    UNSURE,
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
    UncalibratedModelError,
    current_value,
    run_enrichment,
)
from glean.recipes.enrichment.active_time import active_time_question
from glean.recipes.enrichment.attributes import WHOLE_FOOD_LEVELS, AttributeEnricher, attribute_questions
from glean.recipes.enrichment.enricher import ATTRIBUTE_BAR_MODEL, MIN_ATTRIBUTE_BAR, attribute_bar
from glean.recipes.stored import StoredIngredient, StoredInstruction, StoredRecipe
from tests.recipes.enrichment.fakes import SNAPSHOT, FakeDecisionApi

if TYPE_CHECKING:
    from pathlib import Path


def test_the_questions_wording_is_frozen_so_a_refactor_does_not_re_ask_the_corpus() -> None:
    """Criteria hashes are what stored answers reply to: changing them would re-ask 632 recipes per question.

    These literals are the wording as V5 ships it. A deliberate rewording updates the literal with the PR
    that makes it; an accidental one (a reordered criteria dict, a renamed option) fails here first.
    """
    frozen = {
        "attribute:main_protein": "da264e1316fb351ac97f730d8d0773236d744ba94526f8be69d51bf9fb12bd6b",
        "attribute:main_carb": "7a15d9b33fd6b5df49753ef3dfb0ef5da3207123c0b8c0c04cc56d7d12606b6d",
        "attribute:dish_type": "99d9cc77826fd6cc9badeedbbf8c141caf0670100dd0a30b47c459fb23b48bf1",
        "attribute:cuisine": "ea34656ef2865516a0a85bd291b52b7728e257a1af693a77c86f21a2c0376c8d",
        "attribute:whole_food": "7bb64033fe9e3f832aa77a7f4471b8278d7c5a86b2b54ce0a9a94002834db2fa",
        "active_time:bucket": "d36513eedb634867e1c379c3fdc7fab6ce10b4ae632f867c404c05fd68cd9440",
    }

    asserted = {
        question.name: question.criteria_hash for question in (*ATTRIBUTE_ENRICHER.questions(), active_time_question())
    }

    assert asserted == frozen


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


# The bars the 50-recipe check settled (v5-check/report.md, 2026-10-25). Provisional: one sample of 50.
MEASURED_BARS = {
    "main_protein": 0.80,
    "main_carb": 0.80,
    "dish_type": 0.80,
    "cuisine": 0.85,
    "whole_food": 0.90,
}


def test_every_attribute_ships_at_the_bar_the_check_sample_measured() -> None:
    questions = attribute_questions()

    assert {attribute: question.bar.threshold for attribute, question in questions.items()} == MEASURED_BARS


def test_every_shipped_bar_leans_to_the_high_side_and_stays_above_the_floor() -> None:
    for question in ATTRIBUTE_ENRICHER.questions():
        assert question.bar.safe_side is SafeSide.HIGH
        assert MIN_ATTRIBUTE_BAR <= question.bar.threshold <= 1.0


def test_a_bar_is_tunable_per_attribute_and_only_for_that_attribute() -> None:
    questions = attribute_questions(bars={"cuisine": 0.75})

    assert questions["cuisine"].bar.threshold == 0.75
    assert questions["main_protein"].bar.threshold == 0.80
    assert questions["whole_food"].bar.threshold == 0.90  # the measured bar, untouched by the override


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


def test_an_attribute_below_its_bar_stores_its_top_option_and_its_probability() -> None:
    """The bar is applied when the answer is read, so what is stored is what the model actually said."""
    answer = attribute_questions()["main_protein"].accept(
        _decision(_choice("attribute:main_protein", "chicken", {"chicken": 0.79, "beef": 0.21}))
    )

    assert (answer.probability, answer.value) == (0.79, "chicken")


def test_a_tuned_bar_moves_the_line_when_the_answer_is_read_not_when_it_is_stored() -> None:
    """A retune needs no re-ask: the same stored answer reads differently under a different bar."""
    decision = _decision(_choice("attribute:cuisine", "thai", {"thai": 0.76, "italian": 0.24}))
    stored = attribute_questions()["cuisine"].accept(decision)
    answer = _stored_answer("attribute:cuisine", stored.value, stored.probability)

    def read(bars: dict[str, float]) -> str | None:
        question = next(
            question for question in attribute_questions(bars=bars).values() if question.name == "attribute:cuisine"
        )
        return current_value(question, answer, content_hash=CONTENT)

    assert read({}) == UNSURE  # the shipped 0.85
    assert read({"cuisine": 0.75}) == "thai"  # lower it and the label comes back
    assert read({"cuisine": 0.90}) == UNSURE  # raise it and a label it now rejects goes


def test_whole_food_accepts_the_level_with_the_highest_probability() -> None:
    answer = attribute_questions()["whole_food"].accept(
        _decision(_score("attribute:whole_food", {0: 0.05, 1: 0.05, 2: 0.9}))
    )

    assert (answer.probability, answer.value) == (0.9, "whole")


def test_a_confidence_that_clears_one_attributes_bar_can_miss_anothers() -> None:
    """The measured bars differ: 0.86 is enough for cuisine (0.85) and not for whole food (0.90)."""
    questions = attribute_questions()

    def read(attribute: str, value: str) -> str | None:
        return current_value(
            questions[attribute], _stored_answer(questions[attribute].name, value, 0.86), content_hash=CONTENT
        )

    assert read("cuisine", "thai") == "thai"
    assert read("whole_food", "whole") == UNSURE


def test_whole_food_below_its_bar_is_stored_and_reads_as_unsure() -> None:
    questions = attribute_questions()
    stored = questions["whole_food"].accept(_decision(_score("attribute:whole_food", {0: 0.1, 1: 0.6, 2: 0.3})))

    assert (stored.probability, stored.value) == (0.6, "mixed")
    assert (
        current_value(
            questions["whole_food"], _stored_answer("attribute:whole_food", stored.value, 0.6), content_hash=CONTENT
        )
        == UNSURE
    )


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


def test_active_time_below_its_bar_reads_as_unsure_which_the_filter_reads_as_total_time() -> None:
    question = active_time_question()
    stored = question.accept(_decision(_score(ACTIVE_TIME_QUESTION, {0: 0.1, 1: 0.45, 2: 0.3, 3: 0.1, 4: 0.05})))

    assert (stored.probability, stored.value) == (0.45, "15-30")
    assert (
        current_value(question, _stored_answer(ACTIVE_TIME_QUESTION, stored.value, 0.45), content_hash=CONTENT)
        == UNSURE
    )


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


CONTENT = content_fingerprint("Synthetic Traybake", ["basil pesto"])


def _stored_answer(question_name: str, value: str | None, probability: float) -> RecipeAnswer:
    """An answer as the store holds it, for reading under a bar (the store is not involved in the bar)."""
    return RecipeAnswer(
        recipe_id="rec_synthetic",
        question=question_name,
        probability=probability,
        value=value,
        model=SNAPSHOT,
        content_hash=CONTENT,
        criteria_hash=_criteria_hash_of(question_name),
        computed_at=datetime(2026, 10, 22, tzinfo=UTC),
    )


def _criteria_hash_of(question_name: str) -> str:
    questions = {question.name: question for question in (*ATTRIBUTE_ENRICHER.questions(), active_time_question())}
    return questions[question_name].criteria_hash


def test_every_attribute_and_active_time_question_accepts_only_the_model_its_bar_was_measured_on() -> None:
    questions = (*ATTRIBUTE_ENRICHER.questions(), *ACTIVE_TIME_ENRICHER.questions())

    assert {question.model for question in questions} == {ATTRIBUTE_BAR_MODEL}
    assert all(not question.model.accepts("baseten/mammoth-1-20261021") for question in questions)


def test_an_attribute_run_asking_another_model_is_refused_before_any_request(tmp_path: Path) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi(snapshot="baseten/mammoth-1-20261021")
    other = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))

    with pytest.raises(UncalibratedModelError):
        run_enrichment(corpus, api.client(model=other), enrichers=(ATTRIBUTE_ENRICHER, ACTIVE_TIME_ENRICHER))

    assert api.requests == []
    assert corpus.answers() == []
