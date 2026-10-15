from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))

from judge_study.results import Judgement, OutputItem
from judge_study.scoring_page import make_server, select_for_scoring

if TYPE_CHECKING:
    from collections.abc import Iterator
    from http.server import ThreadingHTTPServer


def _item(feature: str, n: int, output: dict[str, Any] | None = None) -> OutputItem:
    return OutputItem(
        item_id=f"{feature}/0/{n}",
        feature=feature,
        input={"text": f"input {n}"},
        output=output or {"title": f"output {n}"},
        judge_inputs={},
        judgements=[Judgement(judge="llm", repeat=1, score=5, model="secret/judge-model", latency_s=1)],
    )


FEATURES = ["receipt_scan", "meal_plan", "recipe_import", "pantry_description", "shopping_list_description"]


def _serve(items: list[OutputItem], scores_path: Path) -> tuple[ThreadingHTTPServer, str]:
    server = make_server("127.0.0.1", 0, items, scores_path)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


@pytest.fixture
def scores_path(tmp_path: Path) -> Path:
    return tmp_path / "human_scores.json"


@pytest.fixture
def served(scores_path: Path) -> Iterator[str]:
    server, url = _serve([_item("meal_plan", 0), _item("recipe_import", 1)], scores_path)
    yield url
    server.shutdown()
    server.server_close()


def _post(url: str, payload: dict[str, Any]) -> int:
    request = urllib.request.Request(  # noqa: S310
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def _get(url: str) -> str:
    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read().decode()


class TestScoringPage:
    def test_the_page_shows_each_output_with_its_rubric_and_a_one_to_five_choice(self, served: str) -> None:
        page = _get(served)

        assert "output 0" in page
        assert "input 1" in page
        assert "Excellent — uses expiring/urgent pantry items" in page  # the meal-plan rubric
        assert page.count('value="5"') == 2

    def test_the_page_does_not_reveal_what_either_judge_scored(self, served: str) -> None:
        assert "secret/judge-model" not in _get(served)

    def test_output_text_is_escaped_so_a_recipe_cannot_run_script_on_the_page(self, scores_path: Path) -> None:
        server, url = _serve([_item("recipe_import", 0, output={"title": "<script>alert(1)</script>"})], scores_path)
        try:
            page = _get(url)
        finally:
            server.shutdown()
            server.server_close()

        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page

    def test_a_score_is_written_to_the_scores_file(self, served: str, scores_path: Path) -> None:
        status = _post(f"{served}/score", {"item_id": "meal_plan/0/0", "score": 4})

        assert status == 200
        assert json.loads(scores_path.read_text()) == {"meal_plan/0/0": 4}

    def test_a_score_can_be_changed(self, served: str, scores_path: Path) -> None:
        _post(f"{served}/score", {"item_id": "meal_plan/0/0", "score": 4})
        _post(f"{served}/score", {"item_id": "meal_plan/0/0", "score": 2})

        assert json.loads(scores_path.read_text()) == {"meal_plan/0/0": 2}

    @pytest.mark.parametrize("payload", [{"item_id": "meal_plan/0/0", "score": 6}, {"item_id": "nope", "score": 3}, {}])
    def test_a_bad_score_is_refused_and_nothing_is_written(
        self, served: str, scores_path: Path, payload: dict[str, Any]
    ) -> None:
        assert _post(f"{served}/score", payload) == 400
        assert not scores_path.exists()

    def test_scores_survive_a_restart_and_show_as_already_chosen(self, scores_path: Path) -> None:
        scores_path.write_text(json.dumps({"meal_plan/0/0": 3}))
        server, url = _serve([_item("meal_plan", 0)], scores_path)
        try:
            page = _get(url)
        finally:
            server.shutdown()
            server.server_close()

        assert "1 of 1 scored" in page
        assert 'value="3" checked' in page


class TestSelectForScoring:
    def test_it_takes_the_requested_number_spread_across_every_feature(self) -> None:
        items = [_item(feature, n) for feature in FEATURES for n in range(8)]

        chosen = select_for_scoring(items, count=25, seed=1)

        assert len(chosen) == 25
        assert {item.feature for item in chosen} == set(FEATURES)
        assert min(sum(item.feature == f for item in chosen) for f in FEATURES) >= 4

    def test_a_small_feature_is_taken_whole_and_the_rest_fill_the_count(self) -> None:
        items = [_item("recipe_import", n) for n in range(3)] + [_item("meal_plan", n) for n in range(30)]

        chosen = select_for_scoring(items, count=20, seed=1)

        assert sum(item.feature == "recipe_import" for item in chosen) == 3
        assert len(chosen) == 20

    def test_fewer_outputs_than_the_count_are_all_taken(self) -> None:
        items = [_item("meal_plan", n) for n in range(4)]

        assert select_for_scoring(items, count=25, seed=1) == items

    def test_the_same_seed_chooses_the_same_outputs(self) -> None:
        items = [_item(feature, n) for feature in FEATURES for n in range(8)]

        assert select_for_scoring(items, 25, seed=7) == select_for_scoring(items, 25, seed=7)
