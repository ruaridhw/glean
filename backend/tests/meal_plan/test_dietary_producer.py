"""The producer that fills the stored dietary decisions (#125).

Seams: `produce_missing_decisions` (the command's entry point), the stored decisions
it writes, and the `DecisionClient` requests it makes. The decision API itself is faked at the
HTTP boundary with `httpx.MockTransport`.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import SecretStr

from glean.decisions import DECISION_MODEL, DecisionClient, DecisionModel
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    DIETARY_FLAGS,
    CorpusUnavailableError,
    DietaryDecision,
    DietaryDecisionStore,
    UncalibratedModelError,
    content_fingerprint,
    dietary_questions,
    produce_missing_decisions,
    question_hash,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.search_index import INDEX_KEY
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Callable

SNAPSHOT = f"{DECISION_MODEL}-20261014"
# A free route's request id and the identity it answers under differ, as observed in a pilot.
CANDIDATE = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))
CANDIDATE_SERVED = "baseten/mammoth-1-20261021"


class FakeDecisionApi:
    """Answers every question with 0.9 when the state mentions pesto, else 0.01. Records requests."""

    def __init__(self, *, snapshot: str = SNAPSHOT, fail_when: Callable[[dict], bool] | None = None) -> None:
        self.requests: list[dict] = []
        self._snapshot = snapshot
        self._fail_when = fail_when

    def client(self, *, model: DecisionModel | None = None) -> DecisionClient:
        pinned = model or DecisionModel(DECISION_MODEL)
        return DecisionClient(
            api_key=SecretStr("sk-or-test"), model=pinned, transport=httpx.MockTransport(self._handle)
        )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if self._fail_when is not None and self._fail_when(body):
            return httpx.Response(500, text="boom")
        probability = 0.9 if "pesto" in json.dumps(body["state"]) else 0.01
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": self._snapshot,
                "provider": "TypeSafe",
                "answers": {name: {"type": "noul", "noul": probability} for name in body["questions"]},
                "usage": {"input_tokens": 10, "output_tokens": 2, "cost": 0.00001},
            },
        )


def test_first_run_stores_a_decision_for_every_recipe_and_flag_and_reports_full_coverage(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi()

    report = produce_missing_decisions(corpus, api.client())

    stored = {(d.recipe_id, d.flag): d for d in DietaryDecisionStore(corpus.store).load()}
    assert set(stored) == {(rid, flag) for rid in ("rec_pesto", "rec_tomato") for flag in DIETARY_FLAGS}
    assert {flag for _, flag in stored} == {
        "vegetarian",
        "vegan",
        "dairy-free",
        "gluten-free",
        "tree-nut-free",
        "peanut-free",
    }
    assert stored[("rec_pesto", "tree-nut-free")].probability == 0.9
    assert stored[("rec_pesto", "peanut-free")].probability == 0.9
    assert stored[("rec_tomato", "tree-nut-free")].probability == 0.01
    assert stored[("rec_pesto", "tree-nut-free")].model == SNAPSHOT
    assert (report.recipes, report.computed, report.coverage) == (2, 12, 1.0)
    assert report.uncovered == []


def test_second_run_computes_nothing(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeDecisionApi().client())
    second = FakeDecisionApi()

    report = produce_missing_decisions(corpus, second.client())

    assert second.requests == []
    assert (report.computed, report.coverage) == (0, 1.0)


def test_a_recipe_added_later_is_the_only_one_computed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeDecisionApi().client())
    _save(corpus, "rec_new", "Courgette Soup", ["courgette", "stock"])
    api = FakeDecisionApi()

    report = produce_missing_decisions(corpus, api.client())

    assert [request["state"]["recipe_title"] for request in api.requests] == ["Courgette Soup"]
    assert (report.computed, report.coverage) == (6, 1.0)


def test_decisions_from_an_older_model_are_recomputed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    _seed_decisions(corpus, model="typesafe/jev-1.13-20260917")
    api = FakeDecisionApi()

    report = produce_missing_decisions(corpus, api.client())

    assert len(api.requests) == 2
    assert (report.computed, report.coverage) == (12, 1.0)
    assert {d.model for d in DietaryDecisionStore(corpus.store).load()} == {SNAPSHOT}


def test_decisions_computed_under_other_criteria_text_are_recomputed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    question = dietary_questions()["vegan"]
    reworded = question.model_copy(update={"instructions": question.instructions + " Honey counts."})
    _seed_decisions(corpus, model=SNAPSHOT, criteria_hash=lambda flag: question_hash(reworded))
    api = FakeDecisionApi()

    report = produce_missing_decisions(corpus, api.client())

    assert len(api.requests) == 2
    assert (report.computed, report.coverage) == (12, 1.0)
    assert {(d.flag, d.criteria_hash) for d in DietaryDecisionStore(corpus.store).load()} == {
        (flag, question_hash(dietary_questions()[flag])) for flag in DIETARY_FLAGS
    }


def test_one_request_per_recipe_carries_its_title_ingredients_and_every_missing_flag(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi()

    produce_missing_decisions(corpus, api.client())

    pesto_request = next(r for r in api.requests if r["state"]["recipe_title"] == "Pesto Pasta")
    assert pesto_request["model"] == DECISION_MODEL
    assert pesto_request["state"] == {"recipe_title": "Pesto Pasta", "ingredients": ["spaghetti", "basil pesto"]}
    assert set(pesto_request["questions"]) == set(DIETARY_FLAGS)
    assert {question["type"] for question in pesto_request["questions"].values()} == {"noul"}


def test_a_recipe_whose_ingredients_change_is_excluded_until_its_decision_is_recomputed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeDecisionApi().client())
    assert "rec_tomato" in _nut_free_ids(corpus)

    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "basil pesto"])  # same id, tomato swapped for pesto

    assert "rec_tomato" not in _nut_free_ids(corpus)  # the old "safe" answer assessed different content
    api = FakeDecisionApi()
    report = produce_missing_decisions(corpus, api.client())
    assert [request["state"]["recipe_title"] for request in api.requests] == ["Tomato Pasta"]
    assert (report.computed, report.coverage) == (6, 1.0)
    assert "rec_tomato" not in _nut_free_ids(corpus)  # recomputed: the model now says pesto contains nuts


def test_a_changed_recipe_the_model_cant_answer_is_reported_uncovered(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeDecisionApi().client())
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato", "basil pesto"])

    report = produce_missing_decisions(corpus, FakeDecisionApi(fail_when=lambda _body: True).client())

    assert report.uncovered == ["rec_tomato"]
    assert report.coverage < 1.0


def test_a_corpus_whose_search_index_is_missing_fails_loudly_instead_of_reporting_coverage(tmp_path) -> None:
    _corpus(tmp_path)  # recipe blobs exist...
    (tmp_path / INDEX_KEY).unlink()  # ...but Generate, which selects through the index, can see none of them
    api = FakeDecisionApi()

    with pytest.raises(CorpusUnavailableError):
        produce_missing_decisions(RecipeCorpusStore(FilesystemBlobStore(tmp_path)), api.client())

    assert api.requests == []


def test_an_empty_corpus_fails_loudly(tmp_path) -> None:
    with pytest.raises(CorpusUnavailableError):
        produce_missing_decisions(RecipeCorpusStore(FilesystemBlobStore(tmp_path)), FakeDecisionApi().client())


def test_the_questions_state_the_households_ingredient_policy(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi()

    produce_missing_decisions(corpus, api.client())

    def wording(flag: str) -> str:
        question = api.requests[0]["questions"][flag]
        return f"{question['instructions']} {question['criteria']['true']} {question['criteria']['false']}".casefold()

    assert "pine nuts count" in wording("tree-nut-free")
    assert "pesto counts" in wording("tree-nut-free")
    assert "satay" in wording("tree-nut-free")  # named as not a tree nut
    assert "coconut" in wording("tree-nut-free")
    assert "nutmeg" in wording("tree-nut-free")
    assert "satay" in wording("peanut-free")
    assert "peanut butter" in wording("peanut-free")
    assert "groundnut oil" in wording("peanut-free")
    assert "coconut" in wording("peanut-free")
    assert "nutmeg" in wording("peanut-free")
    assert "parmesan and pesto are allowed" in wording("vegetarian")
    assert "pesto" in wording("vegan")
    assert "unless the recipe says gluten-free oats" in wording("gluten-free")


def test_a_recipe_the_model_couldnt_answer_stays_uncovered_while_the_others_are_stored(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi(fail_when=lambda body: body["state"]["recipe_title"] == "Pesto Pasta")

    report = produce_missing_decisions(corpus, api.client())

    assert {d.recipe_id for d in DietaryDecisionStore(corpus.store).load()} == {"rec_tomato"}
    assert report.uncovered == ["rec_pesto"]
    assert report.coverage == 0.5
    assert report.failures == 1


def _nut_free_ids(corpus: RecipeCorpusStore) -> set[str]:
    candidates = sample_corpus_candidates(
        corpus,
        pantry=[],
        dietary_flags=["tree-nut-free", "peanut-free"],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=50,
    )
    return {candidate.external_id for candidate in candidates}


def _seed_decisions(
    corpus: RecipeCorpusStore, *, model: str, criteria_hash: Callable[[str], str] | None = None
) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=rid,
                flag=flag,
                probability=0.0,
                model=model,
                content_hash=content_fingerprint(title, ingredients),
                criteria_hash=(criteria_hash or (lambda f: question_hash(dietary_questions()[f])))(flag),
                computed_at=datetime(2026, 9, 17, tzinfo=UTC),
            )
            for rid, title, ingredients in (
                ("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"]),
                ("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"]),
            )
            for flag in DIETARY_FLAGS
        ]
    )


def _corpus(tmp_path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    _save(corpus, "rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"])
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"])
    return corpus


def _save(corpus: RecipeCorpusStore, external_id: str, title: str, ingredients: list[str]) -> None:
    corpus.save(
        StoredRecipe(
            external_id=external_id,
            title=title,
            ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
        )
    )


def test_a_store_written_before_the_split_is_upgraded_by_asking_only_the_two_new_flags(tmp_path) -> None:
    """The deploy transition: decisions keyed by the old `nut-free` flag sit beside still-valid preference ones."""
    corpus = _corpus(tmp_path)
    kept = ("vegetarian", "vegan", "dairy-free", "gluten-free")
    parent_store = [
        DietaryDecision(
            recipe_id=rid,
            flag=flag,
            probability=0.0,
            model=SNAPSHOT,
            content_hash=content_fingerprint(title, ingredients),
            criteria_hash=question_hash(dietary_questions()[flag]) if flag in kept else "0" * 64,
            computed_at=datetime(2026, 10, 15, tzinfo=UTC),
        )
        for rid, title, ingredients in (
            ("rec_pesto", "Pesto Pasta", ["spaghetti", "basil pesto"]),
            ("rec_tomato", "Tomato Pasta", ["spaghetti", "tomato"]),
        )
        for flag in (*kept, "nut-free")
    ]
    DietaryDecisionStore(corpus.store).save(parent_store)
    api = FakeDecisionApi()

    report = produce_missing_decisions(corpus, api.client())

    assert {frozenset(request["questions"]) for request in api.requests} == {
        frozenset({"tree-nut-free", "peanut-free"})
    }
    assert (report.computed, report.coverage, report.uncovered) == (4, 1.0, [])
    assert {d.flag for d in DietaryDecisionStore(corpus.store).load()} >= {"tree-nut-free", "peanut-free"}
    second = FakeDecisionApi()
    assert produce_missing_decisions(corpus, second.client()).computed == 0
    assert second.requests == []


def test_a_client_asking_a_model_the_calibration_does_not_cover_is_refused_before_any_request_or_write(
    tmp_path,
) -> None:
    corpus = _corpus(tmp_path)
    api = FakeDecisionApi(snapshot=CANDIDATE_SERVED)

    with pytest.raises(UncalibratedModelError):
        produce_missing_decisions(corpus, api.client(model=CANDIDATE))

    assert api.requests == []
    assert DietaryDecisionStore(corpus.store).load() == []
