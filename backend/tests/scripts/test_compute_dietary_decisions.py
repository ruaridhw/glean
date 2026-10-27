from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr
from scripts import compute_dietary_decisions

from glean.decisions import DECISION_MODEL, DecisionClient, DecisionModel
from glean.meal_plan import dietary_decisions
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.search_index import INDEX_KEY
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _decision_api(status: int = 200) -> DecisionClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, text="boom")
        questions = json.loads(request.content)["questions"]
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": f"{DECISION_MODEL}-20261014",
                "provider": "TypeSafe",
                "answers": {name: {"type": "noul", "noul": 0.01} for name in questions},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
            },
        )

    return DecisionClient(api_key=SecretStr("sk-or-test"), transport=httpx.MockTransport(handle))


def _local_corpus(cache_dir: Path) -> None:
    corpus = RecipeCorpusStore(FilesystemBlobStore(cache_dir / "corpus"))
    corpus.save(
        StoredRecipe(
            external_id="rec_tomato",
            title="Tomato Pasta",
            ingredients=[StoredIngredient(canonical_name="tomato", quantity=1, unit="each")],
        )
    )


def test_the_client_asks_the_model_the_dietary_calibration_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")

    assert compute_dietary_decisions._client(timeout_s=1.0).model == dietary_decisions.CALIBRATED_DIETARY.model

    alternate = replace(
        dietary_decisions.CALIBRATED_DIETARY,
        model=DecisionModel("another/model:free", served=("another/model",)),
    )
    monkeypatch.setattr(compute_dietary_decisions, "CALIBRATED_DIETARY", alternate)

    assert compute_dietary_decisions._client(timeout_s=1.0).model == alternate.model


def test_a_complete_run_prints_the_coverage_report_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _local_corpus(tmp_path)

    code = compute_dietary_decisions.main(["--cache-dir", str(tmp_path)], client=_decision_api())

    assert code == 0
    assert "Coverage: 6/6 (100.0%)" in capsys.readouterr().out


def test_an_incomplete_run_exits_nonzero_so_the_gate_can_fail(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _local_corpus(tmp_path)

    code = compute_dietary_decisions.main(["--cache-dir", str(tmp_path)], client=_decision_api(status=500))

    assert code == 1
    assert "rec_tomato" in capsys.readouterr().out


def test_a_missing_corpus_index_exits_nonzero_instead_of_passing_the_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _local_corpus(tmp_path)
    (tmp_path / "corpus" / INDEX_KEY).unlink()

    code = compute_dietary_decisions.main(["--cache-dir", str(tmp_path)], client=_decision_api())

    assert code != 0
    assert "Coverage: 100" not in capsys.readouterr().out
