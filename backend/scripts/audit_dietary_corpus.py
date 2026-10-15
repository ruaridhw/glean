#!/usr/bin/env python3
"""Audit the dietary decisions against the whole recipe corpus (#159). Never writes to S3 or the app.

Three signals per (recipe, flag): two LLM judges from different vendors reading the full ingredient list
through structured output, and the dietary regex #159 deleted (frozen in
tests/fixtures/decisions/dietary_regex_terms.json). Where all three agree that is ground truth; the
decision model's probabilities are then scored against it. All audit data lives in --data-dir, outside git:
the recipes are third-party content.

    aws s3 sync s3://<bucket>/corpus/ <data-dir>/corpus/ --exclude '*' --include '*.json'   # read-only
    uv run python scripts/audit_dietary_corpus.py decisions --data-dir <data-dir>
    uv run python scripts/audit_dietary_corpus.py judge --judge anthropic --data-dir <data-dir>
    uv run python scripts/audit_dietary_corpus.py judge --judge openai --data-dir <data-dir>
    uv run python scripts/audit_dietary_corpus.py report --data-dir <data-dir>

Needs OPENROUTER_API_KEY in the environment for `decisions` and `judge`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from glean.decisions import DecisionClient, DecisionError, NoulQuestion
from glean.meal_plan.dietary_decisions import (
    DIETARY_FLAGS,
    NUT_FREE,
    NUT_FREE_THRESHOLD,
    PREFERENCE_THRESHOLD,
    dietary_questions,
)
from glean.recipes.stored import StoredRecipe

FLAGS = DIETARY_FLAGS
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
# Two vendors, so the judges don't share blind spots. `extra` is merged into the request body.
JUDGES: dict[str, tuple[str, dict[str, Any]]] = {
    "anthropic": ("anthropic/claude-sonnet-5.5", {"reasoning": {"effort": "low"}}),
    "openai": ("openai/gpt-6.1-sol", {"reasoning": {"effort": "low"}}),
}
_TERMS_PATH = Path(__file__).parents[1] / "tests" / "fixtures" / "decisions" / "dietary_regex_terms.json"
_VERDICTS = ("breaks", "fine", "unsure")

_JUDGE_INSTRUCTIONS = """\
You are a food-safety assistant labelling a recipe from its title and ingredient list.
For each dietary flag answer "breaks" (at least one ingredient is or very likely contains something the flag \
forbids), "fine" (clearly nothing the flag forbids) or "unsure" (it depends on the exact product). \
Name the ingredient responsible in `culprit` when the verdict is "breaks" or "unsure", otherwise null.

- vegetarian: no meat, poultry, fish, shellfish or other slaughter products (gelatine, lard, suet, anchovy, \
shrimp paste, Worcestershire sauce). Parmesan and pesto are acceptable. Meat-free substitutes are fine.
- vegan: no animal products at all: no meat or fish, dairy, eggs, honey. Plant milks and coconut milk are fine.
- dairy-free: no milk, cheese, butter, cream, yoghurt, whey, buttermilk, ghee or products made with them. \
Plant alternatives, cocoa butter and nut butters are fine.
- gluten-free: no wheat, barley, rye, malt or ordinary oats, including pasta, bread, flour, couscous, noodles, \
soy sauce and gnocchi unless labelled gluten-free. Rice, corn, potato and gram flours are fine.
- nut-free: no tree nuts or peanuts or products made from them (pine nuts, pesto, marzipan, praline, satay, \
nut butters, almond milk). Coconut, nutmeg, seeds and butternut squash are not nuts.
"""


class JudgeReplyError(Exception):
    """The judge's structured reply wasn't the requested shape."""


@dataclass(frozen=True)
class AuditRecipe:
    recipe_id: str
    title: str
    ingredient_names: list[str]


@dataclass
class Signals:
    """Every signal for one (recipe, flag)."""

    judges: dict[str, str]
    regex: bool
    probability: float
    baseline_probability: float | None = None  # the decision under the configuration being compared against


@dataclass
class Confusion:
    true_positives: int = 0
    true_negatives: int = 0
    false_negatives: list[str] = field(default_factory=list)  # unsafe recipes kept
    false_positives: list[str] = field(default_factory=list)  # safe recipes excluded


@dataclass
class ZeroFalseNegatives:
    threshold: float | None  # None when no recipe is unsafe, so nothing needs excluding
    false_positives: list[str]


def _words(*words: str) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(re.escape(word) for word in words) + r")(?:s|es)?\b")


def _regex_rules() -> dict[str, tuple[tuple[re.Pattern[str], re.Pattern[str]], ...]]:
    terms = json.loads(_TERMS_PATH.read_text())
    pair = {group: (_words(*lists["forbidden"]), _words(*lists["safe"])) for group, lists in terms.items()}
    meat, dairy, eggs, gluten, nuts = (pair[g] for g in ("meat-and-fish", "dairy", "eggs-and-honey", "gluten", "nuts"))
    return {
        "vegetarian": (meat,),
        "vegan": (meat, dairy, eggs),
        "dairy-free": (dairy,),
        "gluten-free": (gluten,),
        NUT_FREE: (nuts,),
    }


_RULES = _regex_rules()


def regex_excludes(flag: str, ingredient_names: list[str]) -> bool:
    """What the deleted dietary regex decided: a forbidden word in an ingredient with no safe qualifier."""
    names = [name.casefold() for name in ingredient_names]
    return any(forbidden.search(n) and not safe.search(n) for forbidden, safe in _RULES[flag] for n in names)


def ground_truth(judges: list[str], regex: bool) -> str | None:
    """ "breaks" or "fine" when both judges and the regex agree, else None."""
    regex_verdict = "breaks" if regex else "fine"
    verdicts = {*judges, regex_verdict}
    return regex_verdict if verdicts == {regex_verdict} else None


def confusion(labelled: list[tuple[str, str, float]], *, threshold: float) -> Confusion:
    """Score (recipe id, truth, probability) rows: a recipe is excluded at or above the threshold."""
    result = Confusion()
    for recipe_id, truth, probability in labelled:
        excluded = probability >= threshold
        if truth == "breaks":
            if excluded:
                result.true_positives += 1
            else:
                result.false_negatives.append(recipe_id)
        elif excluded:
            result.false_positives.append(recipe_id)
        else:
            result.true_negatives += 1
    return result


def zero_false_negative_threshold(labelled: list[tuple[str, str, float]]) -> ZeroFalseNegatives:
    unsafe = [probability for _, truth, probability in labelled if truth == "breaks"]
    if not unsafe:
        return ZeroFalseNegatives(threshold=None, false_positives=[])
    threshold = min(unsafe)
    return ZeroFalseNegatives(threshold, confusion(labelled, threshold=threshold).false_positives)


def load_recipes(corpus_dir: Path) -> list[AuditRecipe]:
    recipes = []
    for path in sorted(corpus_dir.rglob("*.json")):
        try:
            recipe = StoredRecipe.model_validate_json(path.read_text())
        except ValidationError:
            continue
        recipes.append(
            AuditRecipe(
                recipe.external_id, recipe.title, [ingredient.canonical_name for ingredient in recipe.ingredients]
            )
        )
    return sorted(recipes, key=lambda recipe: recipe.recipe_id)


def judge_schema() -> dict[str, Any]:
    verdict = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": list(_VERDICTS)},
            "culprit": {"type": ["string", "null"]},
        },
        "required": ["verdict", "culprit"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": dict.fromkeys(FLAGS, verdict),
        "required": list(FLAGS),
        "additionalProperties": False,
    }


def parse_judge_reply(reply: str) -> dict[str, str]:
    try:
        body = json.loads(reply)
        verdicts = {flag: body[flag]["verdict"] for flag in FLAGS}
    except (ValueError, KeyError, TypeError) as exc:
        raise JudgeReplyError(f"Judge reply wasn't the requested shape: {reply[:200]!r}") from exc
    if any(verdict not in _VERDICTS for verdict in verdicts.values()):
        raise JudgeReplyError(f"Judge reply has an unknown verdict: {verdicts}")
    return verdicts


def excluded_by_decision(found: Signals, threshold: float) -> bool:
    """#161: the stored decision alone."""
    return found.probability >= threshold


def excluded_by_regex_or_baseline_decision(found: Signals, threshold: float) -> bool:
    """#145: the old regex, or the decision computed under #145's criteria."""
    if found.baseline_probability is None:
        raise ValueError("No baseline decision to judge #145 by")
    return found.regex or found.baseline_probability >= threshold


def render_disagreements(
    recipes: dict[str, AuditRecipe],
    signals: dict[str, Signals],
    *,
    flag: str,
    thresholds: tuple[float, float] | None = None,
) -> str:
    """A Markdown row per recipe where the judges and the regex don't all agree, for a human to label.

    `thresholds` is (#161's, #145's) for the flag; with it each row also says what each configuration does.
    """
    rows = []
    for recipe_id in sorted(signals):
        found = signals[recipe_id]
        if ground_truth(list(found.judges.values()), found.regex) is not None:
            continue
        recipe = recipes[recipe_id]
        verdicts = ", ".join(f"{name}: {verdict}" for name, verdict in sorted(found.judges.items()))
        lines = [
            f"### {recipe.title} (`{recipe_id}`)",
            "",
            f"- Ingredients: {'; '.join(recipe.ingredient_names)}",
            f"- Judges: {verdicts}",
            f"- Old regex: {'breaks' if found.regex else 'fine'}",
            f"- Decision probability (#161 criteria): {found.probability:.2f}",
        ]
        if found.baseline_probability is not None:
            lines.append(f"- Decision probability (#145 criteria): {found.baseline_probability:.2f}")
        if thresholds is not None:
            lines.append(f"- Excluded by #161: {'yes' if excluded_by_decision(found, thresholds[0]) else 'NO'}")
            if found.baseline_probability is not None:
                excluded = excluded_by_regex_or_baseline_decision(found, thresholds[1])
                lines.append(f"- Excluded by #145: {'yes' if excluded else 'NO'}")
        lines += ["- Human label (breaks / fine): ", ""]
        rows.append("\n".join(lines))
    header = f"# {flag} disagreements ({len(rows)} of {len(signals)} recipes)\n\n"
    return header + "\n".join(rows)


def _spend(path: Path) -> float:
    return (
        sum(entry.get("cost", 0.0) for entry in json.loads(path.read_text()).get("entries", {}).values())
        if path.exists()
        else 0.0
    )


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {"entries": {}}


def load_questions(source: Path) -> tuple[dict[str, NoulQuestion], float, float]:
    """The questions and (nut-free, preference) thresholds of another revision of dietary_decisions.py."""
    spec = importlib.util.spec_from_file_location("baseline_dietary_decisions", source)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Can't load {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module.dietary_questions(), module.NUT_FREE_THRESHOLD, module.PREFERENCE_THRESHOLD


def run_decisions(
    data_dir: Path,
    client: DecisionClient,
    *,
    workers: int = 8,
    questions: dict[str, NoulQuestion] | None = None,
    name: str = "decisions",
) -> None:
    questions = questions or dietary_questions()
    path = data_dir / f"{name}.json"
    store = _load(path)
    recipes = [r for r in load_recipes(data_dir / "corpus") if r.recipe_id not in store["entries"]]

    def ask(recipe: AuditRecipe) -> tuple[str, dict[str, Any] | None]:
        try:
            answer = client.decide(
                {"recipe_title": recipe.title, "ingredients": recipe.ingredient_names},
                questions,
            )
        except DecisionError as exc:
            print(f"decision failed for {recipe.recipe_id}: {exc}")
            return recipe.recipe_id, None
        return recipe.recipe_id, {
            "model": answer.model,
            "probabilities": {flag: answer.noul(flag).noul for flag in FLAGS},
            "cost": answer.usage.cost,
        }

    with ThreadPoolExecutor(workers) as pool:
        for recipe_id, entry in pool.map(ask, recipes):
            if entry is not None:
                store["entries"][recipe_id] = entry
    path.write_text(json.dumps(store, indent=1))
    print(f"decisions: {len(store['entries'])} recipes, spend ${_spend(path):.4f}")


def _judge_one(http: httpx.Client, judge: str, recipe: AuditRecipe) -> tuple[dict[str, str], float]:
    model, extra = JUDGES[judge]
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": _JUDGE_INSTRUCTIONS},
            {"role": "user", "content": json.dumps({"title": recipe.title, "ingredients": recipe.ingredient_names})},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "dietary_labels", "strict": True, "schema": judge_schema()},
        },
        "usage": {"include": True},
        **extra,
    }
    response = http.post(CHAT_URL, json=body)
    response.raise_for_status()
    payload = response.json()
    return parse_judge_reply(payload["choices"][0]["message"]["content"]), float(payload["usage"]["cost"])


def run_judge(
    data_dir: Path, judge: str, api_key: SecretStr, *, budget: float, limit: int | None, workers: int = 6
) -> None:
    path = data_dir / f"judge-{judge}.json"
    store = _load(path)
    recipes = [r for r in load_recipes(data_dir / "corpus") if r.recipe_id not in store["entries"]][:limit]
    running = [_spend(path)]
    with httpx.Client(headers={"Authorization": f"Bearer {api_key.get_secret_value()}"}, timeout=180.0) as http:

        def ask(recipe: AuditRecipe) -> tuple[str, dict[str, Any] | None]:
            if running[0] > budget:
                return recipe.recipe_id, None
            try:
                verdicts, cost = _judge_one(http, judge, recipe)
            except (httpx.HTTPError, JudgeReplyError, KeyError) as exc:
                print(f"{judge} failed for {recipe.recipe_id}: {type(exc).__name__}")
                return recipe.recipe_id, None
            running[0] += cost
            return recipe.recipe_id, {"verdicts": verdicts, "cost": cost}

        with ThreadPoolExecutor(workers) as pool:
            for recipe_id, entry in pool.map(ask, recipes):
                if entry is not None:
                    store["entries"][recipe_id] = entry
    path.write_text(json.dumps(store, indent=1))
    print(f"{judge}: {len(store['entries'])} recipes judged, spend ${_spend(path):.4f}")


def build_signals(data_dir: Path) -> tuple[dict[str, AuditRecipe], dict[str, dict[str, Signals]]]:
    """Recipes with every signal present: {flag: {recipe_id: Signals}}."""
    recipes = {r.recipe_id: r for r in load_recipes(data_dir / "corpus")}
    decisions = _load(data_dir / "decisions.json")["entries"]
    baseline = _load(data_dir / "decisions-145.json")["entries"]
    judged = {name: _load(data_dir / f"judge-{name}.json")["entries"] for name in JUDGES}
    complete = [
        rid
        for rid in recipes
        if rid in decisions and rid in baseline and all(rid in entries for entries in judged.values())
    ]
    signals: dict[str, dict[str, Signals]] = {flag: {} for flag in FLAGS}
    for rid in complete:
        for flag in FLAGS:
            signals[flag][rid] = Signals(
                judges={name: entries[rid]["verdicts"][flag] for name, entries in judged.items()},
                regex=regex_excludes(flag, recipes[rid].ingredient_names),
                probability=decisions[rid]["probabilities"][flag],
                baseline_probability=baseline[rid]["probabilities"][flag],
            )
    return recipes, signals


def _effective_probability(found: Signals, *, baseline: bool) -> float:
    """What a configuration's exclusion looks like as one number: the regex counts as certainty under #145."""
    if baseline:
        if found.baseline_probability is None:
            raise ValueError("No baseline decision")
        return 1.0 if found.regex else found.baseline_probability
    return found.probability


def _score(lines: list[str], title: str, labelled: list[tuple[str, str, float]], threshold: float) -> None:
    at_threshold = confusion(labelled, threshold=threshold)
    needed = zero_false_negative_threshold(labelled)
    lines += [
        f"- {title} at {threshold}: unsafe {at_threshold.true_positives + len(at_threshold.false_negatives)}, "
        f"safe {at_threshold.true_negatives + len(at_threshold.false_positives)}; "
        f"FN {len(at_threshold.false_negatives)} {at_threshold.false_negatives}; "
        f"FP {len(at_threshold.false_positives)}; zero-FN threshold {needed.threshold} "
        f"(FP there {len(needed.false_positives)})",
    ]


def run_report(data_dir: Path, *, baseline_thresholds: tuple[float, float]) -> None:
    """Score #161 (decision only) and #145 (regex or decision) against the agreed ground truth.

    Ground truth needs both judges and the regex to agree, so #145 can't miss an agreed-unsafe recipe by
    construction. Its real exposure is the recipes the signals disagree on, so each flag is also scored
    against the judges' consensus alone ("provisional"), which includes recipes the regex missed.
    """
    recipes, signals = build_signals(data_dir)
    lines = [f"Recipes with all signals: {len(signals[FLAGS[0]])} of {len(recipes)}", ""]
    for flag in FLAGS:
        thresholds = {
            "#161": NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD,
            "#145": baseline_thresholds[0] if flag == NUT_FREE else baseline_thresholds[1],
        }
        agreed, provisional = [], []
        for rid, found in signals[flag].items():
            truth = ground_truth(list(found.judges.values()), found.regex)
            if truth is not None:
                agreed.append((rid, found, truth))
            if len(set(found.judges.values())) == 1 and next(iter(found.judges.values())) != "unsure":
                provisional.append((rid, found, next(iter(found.judges.values()))))
        lines.append(
            f"## {flag}: {len(agreed)} agreed, {len(signals[flag]) - len(agreed)} disagreed or unsure; "
            f"{len(provisional)} with judge consensus"
        )
        for set_name, rows in (("agreed truth", agreed), ("judge-consensus truth", provisional)):
            for config, is_baseline in (("#161", False), ("#145", True)):
                labelled = [
                    (rid, truth, _effective_probability(found, baseline=is_baseline)) for rid, found, truth in rows
                ]
                _score(lines, f"{set_name}, {config}", labelled, thresholds[config])
        lines.append("")
    (data_dir / "report.md").write_text("\n".join(lines))
    (data_dir / f"{NUT_FREE}-disagreements.md").write_text(
        render_disagreements(
            recipes,
            signals[NUT_FREE],
            flag=NUT_FREE,
            thresholds=(NUT_FREE_THRESHOLD, baseline_thresholds[0]),
        )
    )
    print("\n".join(lines))


def _api_key() -> SecretStr:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("Set OPENROUTER_API_KEY.")
    return SecretStr(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["decisions", "judge", "report"])
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--judge", choices=sorted(JUDGES))
    parser.add_argument("--budget", type=float, default=2.0, help="Stop judging past this many USD.")
    parser.add_argument("--limit", type=int, default=None, help="Judge at most this many new recipes.")
    parser.add_argument(
        "--baseline-source",
        type=Path,
        help="decisions: another revision of dietary_decisions.py (e.g. #145's) whose criteria to ask under, "
        "stored as decisions-145.json; report: its thresholds are read from here too.",
    )
    args = parser.parse_args(argv)
    baseline = load_questions(args.baseline_source) if args.baseline_source else None
    if args.command == "decisions":
        client = DecisionClient(api_key=_api_key(), timeout_s=60.0)
        if baseline:
            run_decisions(args.data_dir, client, questions=baseline[0], name="decisions-145")
        else:
            run_decisions(args.data_dir, client)
    elif args.command == "judge":
        if not args.judge:
            raise SystemExit("--judge is required")
        run_judge(args.data_dir, args.judge, _api_key(), budget=args.budget, limit=args.limit)
    else:
        if baseline is None:
            raise SystemExit("--baseline-source is required for the report")
        run_report(args.data_dir, baseline_thresholds=(baseline[1], baseline[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
