"""The producer that fills the stored Jev dietary decisions (#125).

Seams: `produce_missing_decisions` (the command's entry point), the stored decisions
it writes, and the `DecisionClient` requests it makes. Jev itself is faked at the
HTTP boundary with `httpx.MockTransport`.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr

from glean.decisions import JEV_MODEL, DecisionClient
from glean.meal_plan.candidates import sample_corpus_candidates
from glean.meal_plan.dietary_decisions import (
    DIETARY_FLAGS,
    DietaryDecision,
    DietaryDecisionStore,
    content_fingerprint,
    produce_missing_decisions,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Callable

SNAPSHOT = f"{JEV_MODEL}-20260917"


class FakeJev:
    """Answers every question with 0.9 when the state mentions pesto, else 0.01. Records requests."""

    def __init__(self, *, snapshot: str = SNAPSHOT, fail_when: Callable[[dict], bool] | None = None) -> None:
        self.requests: list[dict] = []
        self._snapshot = snapshot
        self._fail_when = fail_when

    def client(self) -> DecisionClient:
        return DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(self._handle))

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
    jev = FakeJev()

    report = produce_missing_decisions(corpus, jev.client())

    stored = {(d.recipe_id, d.flag): d for d in DietaryDecisionStore(corpus.store).load()}
    assert set(stored) == {(rid, flag) for rid in ("rec_pesto", "rec_tomato") for flag in DIETARY_FLAGS}
    assert stored[("rec_pesto", "nut-free")].probability == 0.9
    assert stored[("rec_tomato", "nut-free")].probability == 0.01
    assert stored[("rec_pesto", "nut-free")].model == SNAPSHOT
    assert (report.recipes, report.computed, report.coverage) == (2, 10, 1.0)
    assert report.uncovered == []


def test_second_run_computes_nothing(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeJev().client())
    second = FakeJev()

    report = produce_missing_decisions(corpus, second.client())

    assert second.requests == []
    assert (report.computed, report.coverage) == (0, 1.0)


def test_a_recipe_added_later_is_the_only_one_computed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeJev().client())
    _save(corpus, "rec_new", "Courgette Soup", ["courgette", "stock"])
    jev = FakeJev()

    report = produce_missing_decisions(corpus, jev.client())

    assert [request["state"]["recipe_title"] for request in jev.requests] == ["Courgette Soup"]
    assert (report.computed, report.coverage) == (5, 1.0)


def test_decisions_from_an_older_model_are_recomputed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    _seed_old_model_decisions(corpus)
    jev = FakeJev()

    report = produce_missing_decisions(corpus, jev.client())

    assert len(jev.requests) == 2
    assert (report.computed, report.coverage) == (10, 1.0)
    assert {d.model for d in DietaryDecisionStore(corpus.store).load()} == {SNAPSHOT}


def test_one_request_per_recipe_carries_its_title_ingredients_and_every_missing_flag(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    jev = FakeJev()

    produce_missing_decisions(corpus, jev.client())

    pesto_request = next(r for r in jev.requests if r["state"]["recipe_title"] == "Pesto Pasta")
    assert pesto_request["model"] == JEV_MODEL
    assert pesto_request["state"] == {"recipe_title": "Pesto Pasta", "ingredients": ["spaghetti", "basil pesto"]}
    assert set(pesto_request["questions"]) == set(DIETARY_FLAGS)
    assert {question["type"] for question in pesto_request["questions"].values()} == {"noul"}


def test_a_recipe_whose_ingredients_change_is_excluded_until_its_decision_is_recomputed(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeJev().client())
    assert "rec_tomato" in _nut_free_ids(corpus)

    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "basil pesto"])  # same id, tomato swapped for pesto

    assert "rec_tomato" not in _nut_free_ids(corpus)  # the old "safe" answer assessed different content
    jev = FakeJev()
    report = produce_missing_decisions(corpus, jev.client())
    assert [request["state"]["recipe_title"] for request in jev.requests] == ["Tomato Pasta"]
    assert (report.computed, report.coverage) == (5, 1.0)
    assert "rec_tomato" not in _nut_free_ids(corpus)  # recomputed: Jev now says pesto contains nuts


def test_a_changed_recipe_jev_cant_answer_is_reported_uncovered(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    produce_missing_decisions(corpus, FakeJev().client())
    _save(corpus, "rec_tomato", "Tomato Pasta", ["spaghetti", "tomato", "basil pesto"])

    report = produce_missing_decisions(corpus, FakeJev(fail_when=lambda _body: True).client())

    assert report.uncovered == ["rec_tomato"]
    assert report.coverage < 1.0


def test_the_questions_state_the_households_ingredient_policy(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    jev = FakeJev()

    produce_missing_decisions(corpus, jev.client())

    def wording(flag: str) -> str:
        question = jev.requests[0]["questions"][flag]
        return f"{question['instructions']} {question['criteria']['true']} {question['criteria']['false']}".casefold()

    assert "pine nuts count as nuts" in wording("nut-free")
    assert "coconut" in wording("nut-free")
    assert "nutmeg" in wording("nut-free")
    assert "parmesan" in wording("vegetarian")
    assert "unless the recipe says gluten-free oats" in wording("gluten-free")


def test_a_recipe_jev_couldnt_answer_stays_uncovered_while_the_others_are_stored(tmp_path) -> None:
    corpus = _corpus(tmp_path)
    jev = FakeJev(fail_when=lambda body: body["state"]["recipe_title"] == "Pesto Pasta")

    report = produce_missing_decisions(corpus, jev.client())

    assert {d.recipe_id for d in DietaryDecisionStore(corpus.store).load()} == {"rec_tomato"}
    assert report.uncovered == ["rec_pesto"]
    assert report.coverage == 0.5
    assert report.failures == 1


def _nut_free_ids(corpus: RecipeCorpusStore) -> set[str]:
    candidates = sample_corpus_candidates(
        corpus,
        pantry_names=[],
        dietary_flags=["nut-free"],
        max_total_time_mins=None,
        exclude_external_ids=[],
        rng=random.Random(0),
        sample_size=50,
    )
    return {candidate.external_id for candidate in candidates}


def _seed_old_model_decisions(corpus: RecipeCorpusStore) -> None:
    DietaryDecisionStore(corpus.store).save(
        [
            DietaryDecision(
                recipe_id=rid,
                flag=flag,
                probability=0.0,
                model="typesafe/jev-1.12-20260801",
                content_hash=content_fingerprint(title, ingredients),
                computed_at=datetime(2026, 8, 1, tzinfo=UTC),
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
