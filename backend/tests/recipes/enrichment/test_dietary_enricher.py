"""The dietary enricher: the questions and thresholds the corpus was already answered under.

The point of these tests is that moving the dietary producer into the enrichment package changed nothing
about what is asked or what is accepted: the criteria hashes are frozen as literals, a corpus the F1
migration filled produces no requests at all, and planning excludes exactly the same recipes before and
after a run.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from scripts import migrate_recipe_corpus

from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    PEANUT_FREE,
    PREFERENCE_THRESHOLD,
    THRESHOLDS,
    TREE_NUT_FREE,
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
)
from glean.recipes.answers import DIETARY_DECISIONS_KEY, dietary_question
from glean.recipes.corpus import BlobCorpusBackend, RecipeCorpusStore
from glean.recipes.dynamo_corpus import DynamoCorpusBackend
from glean.recipes.enrichment import DIETARY_ENRICHER, SafeSide, run_enrichment
from glean.recipes.enrichment.dietary import DIETARY_FLAGS, dietary_enrichment_questions
from glean.recipes.stored import StoredIngredient, StoredRecipe
from tests.conftest import RECIPES_TABLE_NAME
from tests.recipes.enrichment.fakes import SNAPSHOT, FakeDecisionApi
from tests.recipes.fake_projection import InMemoryProjectionStore

if TYPE_CHECKING:
    from pathlib import Path

# The criteria hashes as computed before the producer moved into the enrichment package. A stored answer is
# only current while its criteria hash matches, so an edit to any question's wording voids the whole corpus
# and has to be a deliberate act: this test is what makes it one.
FROZEN_CRITERIA_HASHES = {
    "vegetarian": "d544d426947df2ba59125357136d8b2c9519237a9116023e64da10265074291d",
    "vegan": "d9b8be9cdea0f18fde8ba2932b41eb285554a11664837e19892e6442edb3ef45",
    "dairy-free": "3ea90d640967c9e203a80c7f123d4929d01599329baf73c0346137ad746b6dfd",
    "gluten-free": "7fefc95c0de8b42d53b91072ad44283a68ae81e916b1692d09912d0541670331",
    "tree-nut-free": "9598789ab4b581bdc1bf3ec3da176bd4fd9d935a4d0de3f41c4163e3b792f140",
    "peanut-free": "4b01957a185526129ab8168ff8f6e71d27bb6e1d4f4d1f477e32a6d1054e4d46",
}


@pytest.fixture
def projections() -> InMemoryProjectionStore:
    return InMemoryProjectionStore()


def test_the_questions_keep_the_criteria_hashes_the_corpus_was_answered_under() -> None:
    questions = dietary_enrichment_questions()

    assert {flag: question.criteria_hash for flag, question in questions.items()} == FROZEN_CRITERIA_HASHES
    assert set(questions) == set(DIETARY_FLAGS)


def test_the_answers_are_stored_under_f1s_question_names() -> None:
    assert [question.name for question in DIETARY_ENRICHER.questions()] == [
        dietary_question(flag) for flag in DIETARY_FLAGS
    ]


def test_the_thresholds_are_the_ones_adr_0011_calibrated() -> None:
    questions = dietary_enrichment_questions()

    assert (THRESHOLDS[TREE_NUT_FREE], THRESHOLDS[PEANUT_FREE], PREFERENCE_THRESHOLD) == (0.3, 0.3, 0.5)
    # The bars are the exclusion thresholds: safe at a low probability, never a confidence floor.
    assert {question.bar.safe_side for question in questions.values()} == {SafeSide.LOW}
    assert {flag: question.bar.threshold for flag, question in questions.items()} == {
        flag: THRESHOLDS.get(flag, PREFERENCE_THRESHOLD) for flag in DIETARY_FLAGS
    }


def test_a_corpus_filled_by_f1s_migration_produces_no_requests(tmp_path: Path, recipes_table, projections) -> None:
    source = _legacy_blob_corpus(tmp_path)  # the pre-F1 JSONL: `flag`, no `question`, current criteria
    target = DynamoCorpusBackend(RECIPES_TABLE_NAME, projection=projections)
    assert (
        migrate_recipe_corpus.main(
            ["--table", RECIPES_TABLE_NAME, "--local", str(tmp_path)],
            corpus_source=source,
            backend=target,
            projection_store=projections,
        )
        == 0
    )
    api = FakeDecisionApi()

    report = run_enrichment(RecipeCorpusStore(target), api.client(), enrichers=(DIETARY_ENRICHER,))

    assert api.requests == []  # the migration's answers are already current
    assert (report.answers_stored, report.coverage) == (0, 1.0)


def test_planning_excludes_the_same_recipes_before_and_after_a_run(tmp_path: Path) -> None:
    corpus = _blob_corpus(tmp_path)
    _store_current_answers(corpus)
    before = {flag: _ids(corpus, flag) for flag in DIETARY_FLAGS}
    assert before["tree-nut-free"] == {"rec_tomato"}  # the stored probability already decided this

    run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,))

    assert {flag: _ids(corpus, flag) for flag in DIETARY_FLAGS} == before


def test_a_probability_the_model_is_unsure_about_is_still_stored_and_decided_at_read_time(tmp_path: Path) -> None:
    corpus = _blob_corpus(tmp_path)

    # 0.3 is the tree-nut exclusion threshold: the answer is stored as it came, and it excludes.
    run_enrichment(corpus, FakeDecisionApi(low=0.3).client(), enrichers=(DIETARY_ENRICHER,))

    stored = {answer.question: answer.probability for answer in corpus.answers() if answer.recipe_id == "rec_tomato"}
    assert stored[dietary_question(TREE_NUT_FREE)] == 0.3
    assert _ids(corpus, TREE_NUT_FREE) == set()


def test_a_question_the_model_is_not_asked_about_is_never_reported(tmp_path: Path) -> None:
    corpus = _blob_corpus(tmp_path)

    report = run_enrichment(corpus, FakeDecisionApi().client(), enrichers=(DIETARY_ENRICHER,))

    assert {coverage.name for coverage in report.questions} == {dietary_question(flag) for flag in DIETARY_FLAGS}


def test_the_questions_state_the_households_ingredient_policy(tmp_path: Path) -> None:
    corpus = _blob_corpus(tmp_path)
    api = FakeDecisionApi()

    run_enrichment(corpus, api.client())

    questions = api.requests[0]["questions"]

    def wording(flag: str) -> str:
        question = questions[dietary_question(flag)]
        criteria = question["criteria"]
        return f"{question['instructions']} {criteria['true']} {criteria['false']}".casefold()

    assert "pine nuts count" in wording("tree-nut-free")
    assert "pesto counts" in wording("tree-nut-free")
    assert "satay" in wording("tree-nut-free")  # named as not a tree nut
    assert "coconut" in wording("tree-nut-free")
    assert "nutmeg" in wording("tree-nut-free")
    assert "satay" in wording("peanut-free")
    assert "peanut butter" in wording("peanut-free")
    assert "groundnut oil" in wording("peanut-free")
    assert "parmesan and pesto are allowed" in wording("vegetarian")
    assert "unless the recipe says gluten-free oats" in wording("gluten-free")


def _legacy_blob_corpus(tmp_path: Path) -> RecipeCorpusStore:
    """A pre-F1 corpus: recipe blobs plus the dietary JSONL lines a `flag` and no `question`."""
    corpus = _blob_corpus(tmp_path)
    lines = [
        json.dumps(
            {
                "recipe_id": summary.external_id,
                "flag": flag,
                "probability": 0.9 if _names_nuts(summary) else 0.01,
                "model": SNAPSHOT,
                "content_hash": content_fingerprint(summary.title, summary.ingredient_names),
                "criteria_hash": FROZEN_CRITERIA_HASHES[flag],
                "computed_at": "2026-10-20T09:00:00Z",
            }
        )
        for summary in corpus.search(per_page=1000)[0]
        for flag in DIETARY_FLAGS
    ]
    BlobCorpusBackend(corpus.store.blobs).write(DIETARY_DECISIONS_KEY, "\n".join(lines) + "\n")
    return corpus


def _store_current_answers(corpus: RecipeCorpusStore) -> None:
    """The answers a pre-enrichment corpus holds: current criteria, probabilities that already decide it."""
    questions = dietary_enrichment_questions()
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=summary.external_id,
                flag=flag,
                probability=0.9 if _names_nuts(summary) else 0.01,
                model=SNAPSHOT,
                content_hash=content_fingerprint(summary.title, summary.ingredient_names),
                criteria_hash=questions[flag].criteria_hash,
                computed_at=datetime(2026, 10, 20, tzinfo=UTC),
            )
            for summary in corpus.search(per_page=1000)[0]
            for flag in DIETARY_FLAGS
        ]
    )


def _names_nuts(summary) -> bool:
    """Whether the fake reads this recipe as containing a nut (it looks for the word in the ingredients)."""
    return any("pesto" in name for name in summary.ingredient_names)


def _ids(corpus: RecipeCorpusStore, flag: str) -> set[str]:
    candidates = sample_corpus_candidates(
        corpus,
        pantry=[],
        dietary_flags=[flag],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=50,
    )
    return {candidate.external_id for candidate in candidates}


def _blob_corpus(tmp_path: Path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(BlobCorpusBackend(_blobs(tmp_path)))
    _save(corpus, "rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])
    return corpus


def _blobs(tmp_path: Path):
    from glean.recipe_api.blob_store import FilesystemBlobStore  # noqa: PLC0415

    return FilesystemBlobStore(tmp_path)


def _save(corpus: RecipeCorpusStore, external_id: str, title: str, ingredients: list[str]) -> None:
    corpus.save(
        StoredRecipe(
            external_id=external_id,
            title=title,
            ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
        )
    )
