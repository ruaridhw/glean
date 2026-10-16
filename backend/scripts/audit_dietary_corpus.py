#!/usr/bin/env python3
"""Audit the dietary decisions against the whole recipe corpus (#159). Never writes to S3 or the app.

Three signals per (recipe, flag): two LLM judges from different vendors reading the full ingredient list
through structured output, and the dietary regex #159 deleted (frozen in
tests/fixtures/decisions/dietary_regex_terms.json). Where all three agree that is ground truth; the
decision model's probabilities are then scored against it. Where the judges are both unsure or disagree on
nut-free, the retailer's shelf (Ocado, then Sainsbury's: `--retailer-ground-truth`) is ground truth, ahead of the
maintainer's labels. All audit data lives in --data-dir, outside git:
the recipes are third-party content.

    aws s3 sync s3://<bucket>/corpus/ <data-dir>/corpus/ --exclude '*' --include '*.json'   # read-only
    uv run python -m scripts.audit_dietary_corpus decisions --data-dir <data-dir>
    uv run python -m scripts.audit_dietary_corpus judge --judge anthropic --data-dir <data-dir>
    uv run python -m scripts.audit_dietary_corpus judge --judge openai --data-dir <data-dir>
    uv run python -m scripts.audit_dietary_corpus report --data-dir <data-dir> --baseline-source <145 file>
    uv run --group audit python -m scripts.audit_dietary_corpus report ... --retailer-ground-truth

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
from typing import TYPE_CHECKING, Any

import httpx
from pydantic import SecretStr, ValidationError
from scripts.grocery_ground_truth import (
    ContainsPolicy,
    Frequency,
    IngredientVerdict,
    OcadoReader,
    Product,
    ProductCache,
    SainsburysReader,
    classify,
    is_unsafe,
)
from scripts.grocery_ground_truth import ground_truth as read_retailer_shelf

from glean.decisions import DecisionClient, DecisionError, NoulQuestion
from glean.meal_plan.dietary_decisions import (
    DIETARY_FLAGS,
    NUT_FREE,
    NUT_FREE_THRESHOLD,
    PREFERENCE_THRESHOLD,
    content_fingerprint,
    dietary_questions,
    question_hash,
)
from glean.recipes.stored import StoredRecipe

if TYPE_CHECKING:
    from collections.abc import Callable

FLAGS = DIETARY_FLAGS
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
# Two vendors, so the judges don't share blind spots. `extra` is merged into the request body.
JUDGES: dict[str, tuple[str, dict[str, Any]]] = {
    "anthropic": ("anthropic/claude-sonnet-5.5", {"reasoning": {"effort": "low"}}),
    "openai": ("openai/gpt-6.1-sol", {"reasoning": {"effort": "low"}}),
}
DEFAULT_GROUND_TRUTH_CACHE = Path(__file__).parents[1] / ".cache" / "grocery_ground_truth"
_TERMS_PATH = Path(__file__).parents[1] / "tests" / "fixtures" / "decisions" / "dietary_regex_terms.json"
_VERDICTS = ("breaks", "fine", "unsure")

# "May contain" and factory-trace warnings are ignored for every flag: only ingredients count (maintainer, 2026-10-16).
_JUDGE_INSTRUCTIONS = """\
You are a food-safety assistant labelling a recipe from its title and ingredient list.
For each dietary flag answer "breaks" (at least one ingredient is or very likely contains something the flag \
forbids), "fine" (clearly nothing the flag forbids) or "unsure" (it depends on the exact product). \
Name the ingredient responsible in `culprit` when the verdict is "breaks" or "unsure", otherwise null.

Only the listed ingredients count: ignore "may contain" and "made in a factory that handles" warnings.

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
    select: Callable[[Signals], bool] | None = None,
    title: str | None = None,
) -> str:
    """A Markdown row per recipe where the judges and the regex don't all agree, for a human to label.

    `thresholds` is (#161's, #145's) for the flag; with it each row also says what each configuration does.
    """
    rows = []
    for recipe_id in sorted(signals):
        found = signals[recipe_id]
        wanted = select(found) if select else ground_truth(list(found.judges.values()), found.regex) is None
        if not wanted:
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
    header = f"# {title or f'{flag} disagreements'} ({len(rows)} of {len(signals)} recipes)\n\n"
    return header + "\n".join(rows)


# The maintainer's labels of the nut-free recipes both judges were unsure about (2026-10-16). They override
# every other signal; "may contain" warnings never count. Tree nuts and peanuts are separate concerns: the
# chilli crisp recipe is fine for a tree-nut allergy though #161's single flag stays on the safe side for peanuts.
MAINTAINER_NUT_FREE_LABELS: dict[str, str] = {
    **dict.fromkeys(
        (
            "rec_12d9df09a90bd7c7",  # chilli crisp
            "rec_1d2fa608c4d40f90",
            "rec_3ebf545c2941c2ab",  # pasanda style seasoning
            "rec_41788b7d623c8ece",
            "rec_454acb729d38932f",
            "rec_4c284db6ff22b558",
            "rec_507f058fc653d9b8",
            "rec_5e190fccb7fccf8d",
            "rec_5e25c57521669ed4",
            "rec_69aecc221e53066c",  # pasanda style seasoning
            "rec_6cfe25e9765b7e6b",
            "rec_745851165b5e37aa",
            "rec_7707ee2990019174",
            "rec_889b1bdfc3ffcfb0",
            "rec_8f0bf5137822944c",
        ),
        "fine",
    ),
    # Tikka masala paste and korma curry paste were first labelled exclude and corrected to fine on 2026-10-16
    # ("only nuts in the ingredients count"; supermarket lists show a tree nut in 0 of 9 korma, 1 of 7 tikka pastes).
    "rec_9549ace7527cd5ff": "fine",
    "rec_96e4c5716655075c": "fine",
}


_PROCESSED = re.compile(
    r"\b(?:pastes?|sauces?|seasonings?|pesto|crisp|nduja|sambal|marinades?|masala|spice mix|curry powder)\b",
    re.IGNORECASE,
)
_NOT_A_PRODUCT = re.compile(r"\b(?:for the|to serve)\b", re.IGNORECASE)


def processed_ingredients(ingredient_names: list[str]) -> list[str]:
    """The names a retailer's shelf can answer for: pastes, sauces, seasonings and the like, as products
    ("Milliliter(s) Water for the Sauce" is a quantity of something else)."""
    cleaned = (
        re.sub(r"^milliliters?\(s\)\s+|\s*\(.*?\)", "", name, flags=re.IGNORECASE).strip() for name in ingredient_names
    )
    return [name for name in cleaned if _PROCESSED.search(name) and not _NOT_A_PRODUCT.search(name)]


_NUT_DERIVED = re.compile(r"\b(?:marzipan|praline|frangipane|nutella|gianduja|nougat|baklava|satay)\b", re.IGNORECASE)
_FREE_FROM = re.compile(r"\b(?:nut|peanut)[- ]free\b|\bfree from (?:nuts|peanuts)\b", re.IGNORECASE)


def names_an_allergen(ingredient_name: str) -> bool:
    """The name itself says tree nut or peanut ("almonds", "peanut oil", "marzipan"), whatever a shelf says about
    other ingredients. "Nut-free pesto" does not."""
    name = _FREE_FROM.sub("", ingredient_name)
    facts = classify(Product(retailer="recipe", name=name, url="", ingredients_text=name))
    return bool(facts.tree_nut_ingredients or facts.peanut_ingredients or _NUT_DERIVED.search(name))


def retailer_truth(
    ingredient_names: list[str], lookup: Callable[[str], IngredientVerdict], policy: ContainsPolicy | None
) -> str | None:
    """The whole recipe, not just its pastes: "breaks" when any ingredient is itself a nut or peanut or any
    processed ingredient contains one on the shelf; "fine" only when every processed ingredient is read and safe
    and nothing else names an allergen; otherwise None, because an unsettled ingredient is never assumed safe."""
    processed = processed_ingredients(ingredient_names)
    if not processed:
        return None
    if any(names_an_allergen(name) for name in ingredient_names):
        return "breaks"
    settled = [is_unsafe(lookup(name), policy) for name in processed]
    if any(settled):
        return "breaks"
    return "fine" if all(found is False for found in settled) else None


def _judges_unsettled(found: Signals) -> bool:
    return set(found.judges.values()) == {"unsure"} or len(set(found.judges.values())) > 1


def resolve_truth(
    flag: str,
    recipe_id: str,
    ingredient_names: list[str],
    found: Signals,
    *,
    lookup: Callable[[str], IngredientVerdict] | None = None,
    policy: ContainsPolicy | None = None,
) -> str | None:
    """ "breaks", "fine" or None (unresolved). The retailer's shelf is ground truth, asked only where the judges are
    both unsure or disagree; where it can't settle the recipe a maintainer label decides, else the three signals."""
    if flag == NUT_FREE:
        if lookup is not None and _judges_unsettled(found):
            shelf = retailer_truth(ingredient_names, lookup, policy)
            if shelf is not None:
                return shelf
        label = MAINTAINER_NUT_FREE_LABELS.get(recipe_id)
        if label is not None:
            return "breaks" if label == "exclude" else "fine"
    return ground_truth(list(found.judges.values()), found.regex)


def render_retailer_section(
    recipes: dict[str, AuditRecipe],
    signals: dict[str, Signals],
    *,
    lookup: Callable[[str], IngredientVerdict],
    policy: ContainsPolicy | None,
) -> str:
    """What the retailer's shelf says about each recipe the judges can't settle, next to the maintainer's label."""
    lines = ["## nut-free: recipes the judges can't settle, resolved by the retailer's shelf"]
    for recipe_id in sorted(signals):
        if not _judges_unsettled(signals[recipe_id]):
            continue
        recipe = recipes[recipe_id]
        truth = retailer_truth(recipe.ingredient_names, lookup, policy)
        label = MAINTAINER_NUT_FREE_LABELS.get(recipe_id, "none")
        lines.append(f"- {recipe.title} (`{recipe_id}`): retailer {truth or 'unresolved'}; maintainer label {label}")
        for name in processed_ingredients(recipe.ingredient_names):
            shelf = lookup(name)
            detail = (
                f"{shelf.retailer}, {shelf.products_read} products, tree nut {shelf.tree_nut}, peanut {shelf.peanut}, "
                f"may contain {shelf.may_contain}"
                if shelf.status == "resolved"
                else shelf.status
            )
            lines.append(f"  - {name}: {detail}")
    return "\n".join(lines) + "\n"


def judge_flagged_but_kept(signals: dict[str, Signals], *, threshold: float) -> list[str]:
    """Disagreement recipes where at least one judge says "breaks" but the decision stays below the threshold."""
    return sorted(
        recipe_id
        for recipe_id, found in signals.items()
        if ground_truth(list(found.judges.values()), found.regex) is None
        and "breaks" in found.judges.values()
        and found.probability < threshold
    )


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


def _is_current(entry: dict[str, Any] | None, recipe: AuditRecipe, criteria: dict[str, str]) -> bool:
    return (
        entry is not None
        and entry.get("criteria") == criteria
        and entry.get("content_hash") == content_fingerprint(recipe.title, recipe.ingredient_names)
    )


def run_decisions(
    data_dir: Path,
    client: DecisionClient,
    *,
    workers: int = 8,
    questions: dict[str, NoulQuestion] | None = None,
    name: str = "decisions",
) -> None:
    questions = questions or dietary_questions()
    criteria = {flag: question_hash(question) for flag, question in questions.items()}
    path = data_dir / f"{name}.json"
    store = _load(path)
    # A cached answer only stands for the recipe content and criteria text it was asked under.
    recipes = [
        r for r in load_recipes(data_dir / "corpus") if not _is_current(store["entries"].get(r.recipe_id), r, criteria)
    ]

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
            "criteria": criteria,
            "content_hash": content_fingerprint(recipe.title, recipe.ingredient_names),
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


def build_signals(
    data_dir: Path, *, baseline_questions: dict[str, NoulQuestion]
) -> tuple[dict[str, AuditRecipe], dict[str, dict[str, Signals]]]:
    """Recipes with every signal present: {flag: {recipe_id: Signals}}.

    Refuses decisions computed under other criteria text or recipe content than the current ones.
    """
    recipes = {r.recipe_id: r for r in load_recipes(data_dir / "corpus")}
    decisions = _load(data_dir / "decisions.json")["entries"]
    baseline = _load(data_dir / "decisions-145.json")["entries"]
    for file_name, entries, questions in (
        ("decisions.json", decisions, dietary_questions()),
        ("decisions-145.json", baseline, baseline_questions),
    ):
        criteria = {flag: question_hash(question) for flag, question in questions.items()}
        stale = [rid for rid, recipe in recipes.items() if not _is_current(entries.get(rid), recipe, criteria)]
        if stale:
            raise SystemExit(f"{len(stale)} recipes in {file_name} are missing or stale; re-run `decisions` first.")
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


@dataclass
class ThresholdRow:
    threshold: float
    false_negatives: int
    false_positives: int
    safe: int
    unsafe: int
    lowest_unsafe: float | None
    highest_safe: float | None


def threshold_table(labelled: list[tuple[str, str, float]], thresholds: list[float]) -> list[ThresholdRow]:
    unsafe = [probability for _, truth, probability in labelled if truth == "breaks"]
    safe = [probability for _, truth, probability in labelled if truth != "breaks"]
    rows = []
    for threshold in thresholds:
        counted = confusion(labelled, threshold=threshold)
        rows.append(
            ThresholdRow(
                threshold,
                len(counted.false_negatives),
                len(counted.false_positives),
                len(safe),
                len(unsafe),
                min(unsafe, default=None),
                max(safe, default=None),
            )
        )
    return rows


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


def run_report(
    data_dir: Path,
    *,
    baseline_questions: dict[str, NoulQuestion],
    baseline_thresholds: tuple[float, float],
    lookup: Callable[[str], IngredientVerdict] | None = None,
    policy: ContainsPolicy | None = None,
) -> None:
    """Score #161 (decision only) and #145 (regex or decision) against the agreed ground truth.

    Ground truth needs both judges and the regex to agree, so #145 can't miss an agreed-unsafe recipe by
    construction. Its real exposure is the recipes the signals disagree on, so each flag is also scored
    against the judges' consensus alone ("provisional"), which includes recipes the regex missed.
    """
    recipes, signals = build_signals(data_dir, baseline_questions=baseline_questions)
    lines = [f"Recipes with all signals: {len(signals[FLAGS[0]])} of {len(recipes)}", ""]
    for flag in FLAGS:
        thresholds = {
            "#161": NUT_FREE_THRESHOLD if flag == NUT_FREE else PREFERENCE_THRESHOLD,
            "#145": baseline_thresholds[0] if flag == NUT_FREE else baseline_thresholds[1],
        }
        agreed, provisional = [], []
        for rid, found in signals[flag].items():
            truth = resolve_truth(flag, rid, recipes[rid].ingredient_names, found, lookup=lookup, policy=policy)
            if truth is not None:
                agreed.append((rid, found, truth))
            consensus = next(iter(found.judges.values())) if len(set(found.judges.values())) == 1 else None
            if truth is not None:
                provisional.append((rid, found, truth))
            elif consensus is not None and consensus != "unsure":
                provisional.append((rid, found, consensus))
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
    nut_signals = signals[NUT_FREE]
    lines += ["## nut-free threshold table (ground truth: maintainer labels, then agreed signals)"]
    for config, is_baseline, thresholds in (
        ("#161", False, sorted({0.12, 0.2, NUT_FREE_THRESHOLD, 0.4, 0.5})),
        ("#145", True, [baseline_thresholds[0]]),
    ):
        labelled = [
            (rid, truth, _effective_probability(found, baseline=is_baseline))
            for rid, found in nut_signals.items()
            if (
                truth := resolve_truth(
                    NUT_FREE, rid, recipes[rid].ingredient_names, found, lookup=lookup, policy=policy
                )
            )
            is not None
        ]
        lines += [
            f"- {config} at {row.threshold}: FN {row.false_negatives} of {row.unsafe} unsafe, "
            f"FP {row.false_positives} of {row.safe} safe, lowest unsafe {row.lowest_unsafe}, "
            f"highest safe {row.highest_safe}"
            for row in threshold_table(labelled, thresholds)
        ]
    lines.append("")
    kept_161 = judge_flagged_but_kept(nut_signals, threshold=NUT_FREE_THRESHOLD)
    kept_145 = judge_flagged_but_kept(
        {
            rid: Signals(found.judges, found.regex, 1.0 if found.regex else found.baseline_probability or 0.0)
            for rid, found in nut_signals.items()
        },
        threshold=baseline_thresholds[0],
    )
    lines += [
        f'## nut-free disagreement recipes where a judge says "breaks" but the recipe is kept: '
        f"#161 {len(kept_161)}, #145 {len(kept_145)}",
        f"- #161: {kept_161}",
        "",
    ]
    if lookup is not None:
        lines += render_retailer_section(recipes, nut_signals, lookup=lookup, policy=policy).splitlines()
    (data_dir / "report.md").write_text("\n".join(lines))
    (data_dir / f"{NUT_FREE}-both-unsure.md").write_text(
        render_disagreements(
            recipes,
            nut_signals,
            flag=NUT_FREE,
            thresholds=(NUT_FREE_THRESHOLD, baseline_thresholds[0]),
            select=lambda found: set(found.judges.values()) == {"unsure"},
            title="nut-free: both judges unsure",
        )
    )
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
    parser.add_argument(
        "--retailer-ground-truth",
        action="store_true",
        help="report: settle nut-free recipes the judges can't by reading Ocado (then Sainsbury's) product pages. "
        "Needs the `audit` dependency group (uv run --group audit).",
    )
    parser.add_argument("--ground-truth-cache", type=Path, default=DEFAULT_GROUND_TRUTH_CACHE)
    parser.add_argument("--contains-minimum", choices=[f.value for f in Frequency], default=Frequency.USUALLY.value)
    parser.add_argument("--may-contain-counts", action="store_true", help="Count 'may contain' warnings as containing.")
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
        thresholds = (baseline[1], baseline[2])
        if not args.retailer_ground_truth:
            run_report(args.data_dir, baseline_questions=baseline[0], baseline_thresholds=thresholds)
            return 0
        from scripts.grocery_ground_truth.browser import PlaywrightPageSource  # noqa: PLC0415  (needs the audit group)

        policy = ContainsPolicy(minimum=Frequency(args.contains_minimum), may_contain_counts=args.may_contain_counts)
        cache = ProductCache(args.ground_truth_cache)
        with PlaywrightPageSource() as source:
            readers = [OcadoReader(source), SainsburysReader(source)]
            run_report(
                args.data_dir,
                baseline_questions=baseline[0],
                baseline_thresholds=thresholds,
                lookup=lambda name: read_retailer_shelf(name, 5, readers=readers, cache=cache),
                policy=policy,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
