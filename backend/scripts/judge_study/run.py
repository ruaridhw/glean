"""Live run of the judge study. Spends real OpenRouter money; the unit tests never call it.

    PYTHONPATH=. uv run python scripts/judge_study/run.py freeze  --out DIR
    PYTHONPATH=. uv run python scripts/judge_study/run.py judge   --out DIR [--repeats 3]
    PYTHONPATH=. uv run python scripts/judge_study/run.py serve   --out DIR --host IP --port N [--count 25]
    PYTHONPATH=. uv run python scripts/judge_study/run.py report  --out DIR   # needs narrative.json beside results.json

`DIR` holds results.json, human_items.json and human_scores.json, outside git.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
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
from judge_study.llm_judge import LlmJudge, UsageRecorder, fetch_prices
from judge_study.orchestrate import run_jobs
from judge_study.report import Narrative, build_report
from judge_study.results import Results
from judge_study.scoring_page import make_server, select_for_scoring
from judge_study.stress import stress_variant

if TYPE_CHECKING:
    from collections.abc import Callable

    from judge_study.results import Attempt, FeatureName, OutputItem

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


def add_stress(out: Path) -> None:
    results = Results.load(out / "results.json")
    have = {item.item_id for item in results.items}
    added = [stress_variant(i) for i in results.items if i.origin == "production" and f"{i.item_id}+stress" not in have]
    results.model_copy(update={"items": [*results.items, *added]}).save(out / "results.json")
    print(f"{len(added)} stress variants added")


def _llm_judge_id(feature: FeatureName, router: LLMRouter) -> str:
    return os.environ.get("GLEAN_JUDGE_MODEL") or router.model_id_for(SOURCES[feature][1], purpose=ModelPurpose.EVAL)


def judge(out: Path, repeats: int, cap: float, *, fresh: bool) -> None:
    """The candidate judges, `repeats` times each, every attempt logged. `fresh` drops earlier candidate runs."""
    key = _api_key()
    router = LLMRouter(api_key=key)
    results = Results.load(out / "results.json")
    if fresh:
        results = results.model_copy(
            update={
                "items": [
                    i.model_copy(update={"judgements": [j for j in i.judgements if j.judge.startswith("panel")]})
                    for i in results.items
                ],
                "failures": [f for f in results.failures if f.judge.startswith("panel")],
                "attempts": [a for a in results.attempts if a.judge.startswith("panel")],
            }
        )
    client = DecisionClient(api_key=key, timeout_s=60.0)
    prices = fetch_prices(sorted({_llm_judge_id(i.feature, router) for i in results.items}))

    def make_judge(name: str, item: OutputItem, ledger: list[Attempt]) -> DecisionJudge | LlmJudge:
        if name == "decision":
            return DecisionJudge(client, ledger=ledger)
        model_id = _llm_judge_id(item.feature, router)
        recorder = UsageRecorder()
        model = create_chat_model(model_id, api_key=key, callbacks=[recorder], request_timeout=120_000)
        return LlmJudge(model, model_id=model_id, recorder=recorder, prices=prices[model_id], ledger=ledger)

    jobs = [
        (item.item_id, kind, repeat)
        for repeat in range(1, repeats + 1)
        for item in results.items
        for kind in ("llm", "decision")
    ]
    before = len(results.attempts)
    updated = run_jobs(results, jobs, make_judge, workers=WORKERS, spend_cap=cap)
    models = dict(updated.models)
    for item in updated.items:
        for j in item.judgements:
            models[f"{j.judge}:{item.feature}"] = j.model
    updated = updated.model_copy(update={"models": models})
    updated.save(out / "results.json")
    new = updated.attempts[before:]
    spend = sum(a.cost_usd or 0.0 for a in new)
    print(f"{len(new)} calls made, {sum(a.outcome != 'ok' for a in new)} failed; spend ${spend:.4f} (cap ${cap})")
    for failure in updated.failures:
        print("MISSING", failure.item_id, failure.judge, failure.repeat, failure.error)


PANEL = {"panel_claude": "anthropic/claude-sonnet-5.5", "panel_gpt": "openai/gpt-6.1-sol"}


def panel(out: Path, cap: float) -> None:
    """One blind run of each strong reference judge over every output, stopping before the spend cap."""
    key = _api_key()
    results = Results.load(out / "results.json")
    prices = fetch_prices(list(PANEL.values()))

    def make_judge(name: str, item: OutputItem, ledger: list[Attempt]) -> LlmJudge:
        recorder = UsageRecorder()
        model = create_chat_model(PANEL[name], api_key=key, callbacks=[recorder], request_timeout=180_000)
        return LlmJudge(
            model, model_id=PANEL[name], recorder=recorder, prices=prices[PANEL[name]], judge_name=name, ledger=ledger
        )

    jobs = [(item.item_id, name, 1) for item in results.items for name in PANEL]
    before = len(results.attempts)
    updated = run_jobs(results, jobs, make_judge, workers=WORKERS, spend_cap=cap)
    updated.save(out / "results.json")
    new = updated.attempts[before:]
    print(f"panel spend ${sum(a.cost_usd or 0.0 for a in new):.4f} (cap ${cap}); {len(new)} calls")


def report(out: Path) -> None:
    """Render report.html from results.json and the author's narrative.json (verdict, recommendation, notes)."""
    narrative = json.loads((out / "narrative.json").read_text())
    page = build_report(Results.load(out / "results.json"), Narrative(**narrative))
    (out / "report.html").write_text(page)
    print(f"wrote {out / 'report.html'} ({len(page) // 1024} KiB)")


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
    parser.add_argument("step", choices=["freeze", "stress", "judge", "panel", "serve", "report"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--host", default="100.98.190.46")
    parser.add_argument("--port", type=int, default=8124)
    parser.add_argument("--fresh", action="store_true", help="judge: discard earlier candidate judgements first")
    parser.add_argument("--cap", type=float, default=1.0, help="USD spend cap for the judge or panel step")
    parser.add_argument("--count", type=int, default=25)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.step == "freeze":
        freeze(args.out)
    elif args.step == "stress":
        add_stress(args.out)
    elif args.step == "panel":
        panel(args.out, args.cap)
    elif args.step == "judge":
        judge(args.out, args.repeats, args.cap, fresh=args.fresh)
    elif args.step == "serve":
        serve(args.out, args.host, args.port, args.count)
    else:
        report(args.out)


if __name__ == "__main__":
    print(f"decision model pinned to {DECISION_MODEL}")
    main()
