"""Live run of the judge study. Spends real OpenRouter money; the unit tests never call it.

    PYTHONPATH=. uv run python scripts/judge_study/run.py freeze  --out DIR
    PYTHONPATH=. uv run python scripts/judge_study/run.py judge   --out DIR [--repeats 3]
    PYTHONPATH=. uv run python scripts/judge_study/run.py serve   --out DIR --host IP --port N [--count 25]
    PYTHONPATH=. uv run python scripts/judge_study/run.py report  --out DIR

`DIR` holds results.json, human_items.json and human_scores.json, outside git.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

sys.path.insert(0, str(Path(__file__).parents[1]))

from pydantic import SecretStr
from tests.integration.evals import (
    test_meal_plan_generation,
    test_purchase_description,
    test_receipt_scan,
    test_recipe_import,
    test_shopping_list_description,
)

from glean.decisions import DECISION_MODEL, DecisionClient
from glean.llm import Feature, LLMRouter, ModelPurpose, create_chat_model
from judge_study.decision_judge import DecisionJudge
from judge_study.freeze import freeze_feature
from judge_study.llm_judge import LlmJudge, UsageRecorder, generation_cost_lookup
from judge_study.results import Results
from judge_study.scoring_page import make_server, select_for_scoring

if TYPE_CHECKING:
    from collections.abc import Callable

    from judge_study.results import FeatureName, OutputItem

FIXTURES = Path(__file__).parents[2] / "tests" / "integration" / "evals" / "fixtures"
BACKEND_ENV = Path(__file__).parents[2] / ".env"
WORKERS = 3

# Per feature: fixture file, the router's Feature, and the eval's own production-prompt call for one example.
SOURCES: dict[FeatureName, tuple[str, Feature, Callable[[Any, int, dict[str, Any]], Any]]] = {
    "receipt_scan": (
        "receipt_scan.json",
        Feature.RECEIPT_SCAN,
        lambda model, i, ex: test_receipt_scan._invoke_receipt_scan(model, ex["input"]["line_items"], example_idx=i),
    ),
    "meal_plan": (
        "meal_plan_generation.json",
        Feature.MEAL_PLAN_GENERATION,
        lambda model, i, ex: test_meal_plan_generation._invoke_meal_plan_generation(model, ex["input"], example_idx=i),
    ),
    "recipe_import": (
        "recipe_import.json",
        Feature.RECIPE_IMPORT,
        lambda model, i, ex: test_recipe_import._invoke_recipe_import(model, ex["input"]["html"], example_idx=i),
    ),
    "pantry_description": (
        "purchase_description.json",
        Feature.PANTRY_PURCHASE_DESCRIPTION,
        lambda model, i, ex: test_purchase_description._invoke_purchase_description(
            model, ex["input"]["text"], example_idx=i
        ),
    ),
    "shopping_list_description": (
        "shopping_list_description.json",
        Feature.SHOPPING_LIST_DESCRIPTION,
        lambda model, i, ex: test_shopping_list_description._invoke_shopping_list_description(
            model, ex["input"]["text"], example_idx=i
        ),
    ),
}


def _api_key() -> SecretStr:
    for line in BACKEND_ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return SecretStr(line.split("=", 1)[1].strip().strip("\"'"))
    raise SystemExit("No OPENROUTER_API_KEY in backend/.env")


def freeze(out: Path) -> None:
    key = _api_key()
    router = LLMRouter(api_key=key)
    items: list[OutputItem] = []
    models: dict[str, str] = {}
    for name, (fixture, feature, call) in SOURCES.items():
        # The evals read GLEAN_EVAL_MODEL; this run deliberately ignores it so the production model is what is frozen.
        model_id = router.model_id_for(feature)
        models[f"outputs:{name}"] = model_id
        model = create_chat_model(model_id, api_key=key)
        examples = json.loads((FIXTURES / fixture).read_text())
        items.extend(freeze_feature(name, examples, lambda i, ex, model=model, call=call: call(model, i, ex)))
        print(f"froze {name}: {model_id}")
    Results(models=models, items=items).save(out / "results.json")
    print(f"{len(items)} outputs frozen")


def judge(out: Path, repeats: int) -> None:
    key = _api_key()
    router = LLMRouter(api_key=key)
    results = Results.load(out / "results.json")
    client = DecisionClient(api_key=key, timeout_s=60.0)
    decision_judge = DecisionJudge(client)
    cost_of = generation_cost_lookup(key.get_secret_value())
    models = dict(results.models)
    todo = [
        (item, repeat, kind)
        for repeat in range(1, repeats + 1)
        for item in results.items
        for kind in ("llm", "decision")
    ]
    todo = [
        (item, repeat, kind)
        for item, repeat, kind in todo
        if not any(j.judge == kind and j.repeat == repeat for j in item.judgements)
    ]
    failures: list[str] = []

    def run_one(job: tuple[OutputItem, int, str]) -> None:
        item, repeat, kind = job
        for attempt in (1, 2):
            try:
                if kind == "decision":
                    judgement = decision_judge.judge(item, repeat)
                else:
                    judge_model_id = os.environ.get("GLEAN_JUDGE_MODEL") or router.model_id_for(
                        SOURCES[item.feature][1], purpose=ModelPurpose.EVAL
                    )
                    recorder = UsageRecorder()
                    model = create_chat_model(
                        judge_model_id, api_key=key, callbacks=[recorder], request_timeout=120_000
                    )
                    judgement = LlmJudge(model, model_id=judge_model_id, recorder=recorder, cost_of=cost_of).judge(
                        item, repeat
                    )
                item.judgements.append(judgement)
                models[f"{kind}:{item.feature}"] = judgement.model
                return
            except Exception as error:
                if attempt == 2:
                    failures.append(
                        f"{item.item_id} {kind} repeat {repeat}: {type(error).__name__}: {str(error)[:200]}"
                    )

    with ThreadPoolExecutor(WORKERS) as pool:
        list(pool.map(run_one, todo))
    for item in results.items:
        item.judgements.sort(key=lambda j: (j.judge, j.repeat))
    results.model_copy(update={"models": models}).save(out / "results.json")
    spend = sum(j.cost_usd or 0.0 for item in results.items for j in item.judgements)
    print(f"{len(todo) - len(failures)} judgements added, {len(failures)} failed; judge spend ${spend:.4f}")
    for failure in failures:
        print("FAILED", failure)


def serve(out: Path, host: str, port: int, count: int) -> None:
    results = Results.load(out / "results.json")
    selected_path = out / "human_items.json"
    if selected_path.exists():
        chosen_ids = set(json.loads(selected_path.read_text()))
        chosen = [item for item in results.items if item.item_id in chosen_ids]
    else:
        chosen = select_for_scoring(results.items, count=count, seed=124)
        selected_path.write_text(json.dumps([item.item_id for item in chosen], indent=2) + "\n")
    blind = [item.model_copy(update={"judgements": []}) for item in chosen]
    server = make_server(host, port, blind, out / "human_scores.json")
    print(f"serving {len(blind)} outputs on http://{host}:{port}/", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["freeze", "judge", "serve", "report"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--host", default="100.98.190.46")
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--count", type=int, default=25)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.step == "freeze":
        freeze(args.out)
    elif args.step == "judge":
        judge(args.out, args.repeats)
    elif args.step == "serve":
        serve(args.out, args.host, args.port, args.count)
    else:
        raise SystemExit("report: built after the human scores are in")


if __name__ == "__main__":
    print(f"decision model pinned to {DECISION_MODEL}")
    main()
