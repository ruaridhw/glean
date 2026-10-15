from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
from pydantic import SecretStr
from scripts import compute_dietary_decisions

from glean.decisions import JEV_MODEL, DecisionClient
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _jev(status: int = 200) -> DecisionClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, text="boom")
        questions = json.loads(request.content)["questions"]
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": f"{JEV_MODEL}-20260917",
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


def test_a_complete_run_prints_the_coverage_report_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _local_corpus(tmp_path)

    code = compute_dietary_decisions.main(["--cache-dir", str(tmp_path)], client=_jev())

    assert code == 0
    assert "Coverage: 5/5 (100.0%)" in capsys.readouterr().out


def test_an_incomplete_run_exits_nonzero_so_the_gate_can_fail(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _local_corpus(tmp_path)

    code = compute_dietary_decisions.main(["--cache-dir", str(tmp_path)], client=_jev(status=500))

    assert code == 1
    assert "rec_tomato" in capsys.readouterr().out
