from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import SecretStr
from scripts import evaluate_dietary_model

from glean.decisions import DecisionClient, DecisionModel

if TYPE_CHECKING:
    from pathlib import Path

SERVED = "baseten/mammoth-1-20261021"


def _decision_api() -> DecisionClient:
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        probability = 0.9 if "pesto" in json.dumps(body["state"]) else 0.01
        return httpx.Response(
            200,
            json={
                "id": "gen-dec-test",
                "model": SERVED,
                "provider": "BaseTen",
                "answers": {name: {"type": "noul", "noul": probability} for name in body["questions"]},
                "usage": {"input_tokens": 1, "output_tokens": 1, "cost": 0.0},
            },
        )

    model = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))
    return DecisionClient(api_key=SecretStr("sk-or-test"), model=model, transport=httpx.MockTransport(handle))


def _fixture(tmp_path: Path) -> Path:
    path = tmp_path / "samples.json"
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "id": "sample-nutty",
                        "title": "Pesto Pasta",
                        "ingredients": ["spaghetti", "basil pesto"],
                        "violates": {"tree-nut-free": True, "peanut-free": False},
                    },
                    {
                        "id": "sample-plain",
                        "title": "Tomato Pasta",
                        "ingredients": ["spaghetti", "tomato"],
                        "violates": {"tree-nut-free": False, "peanut-free": False},
                    },
                ]
            }
        )
    )
    return path


def test_the_run_writes_one_local_report_naming_the_model_and_the_reference_cutoffs(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    output = tmp_path / "report.txt"

    code = evaluate_dietary_model.main(
        [
            "--model",
            "baseten/mammoth-1:free",
            "--served-base",
            "baseten/mammoth-1",
            "--fixture",
            str(_fixture(tmp_path)),
            "--output",
            str(output),
        ],
        client=_decision_api(),
    )

    report = output.read_text()
    assert code == 0
    assert "baseten/mammoth-1:free" in report
    assert SERVED in report
    assert "tree-nut-free" in report
    assert "not a calibration" in report.casefold()
    assert "requested model" in capsys.readouterr().out.casefold()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["report.txt", "samples.json"]


def test_it_refuses_options_that_could_point_at_the_live_corpus(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        evaluate_dietary_model.main(
            ["--model", "m", "--fixture", str(_fixture(tmp_path)), "--bucket", "a-recipe-bucket"], client=None
        )

    assert caught.value.code == 2


def test_a_failed_sample_exits_nonzero_so_an_incomplete_run_is_not_read_as_a_pass(tmp_path: Path) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    model = DecisionModel("baseten/mammoth-1:free", served=("baseten/mammoth-1",))
    client = DecisionClient(api_key=SecretStr("sk-or-test"), model=model, transport=httpx.MockTransport(refuse))

    code = evaluate_dietary_model.main(
        ["--model", "baseten/mammoth-1:free", "--fixture", str(_fixture(tmp_path))], client=client
    )

    assert code == 1
