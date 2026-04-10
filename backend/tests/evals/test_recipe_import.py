from __future__ import annotations

import json
import re
from typing import Any

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from glean.recipes.service import URL_PARSE_SYSTEM_PROMPT

from .judges.rubrics import judge_recipe_import


def _invoke_recipe_import(
    model: BaseChatModel, html: str, *, example_idx: int
) -> str:
    result = model.invoke(
        [
            SystemMessage(content=URL_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"Parse this HTML:\n\n{html[:8000]}"),
        ],
        config={"metadata": {"feature": "eval-recipe-import", "example_idx": example_idx}},
    )
    return result.content


class TestRecipeImportStructural:
    """Layer 1: Structural checks (hard gate)."""

    def test_all_examples_return_valid_json(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw, dict), f"Example {i}: expected dict, got {type(raw).__name__}"

    def test_all_examples_have_required_fields(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        required_fields = {"title", "ingredients", "instructions"}
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            missing = required_fields - set(raw.keys())
            assert not missing, f"Example {i}: missing required fields: {missing}"

    def test_ingredients_and_instructions_are_lists(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw["ingredients"], list), f"Example {i}: ingredients is not a list"
            assert isinstance(raw["instructions"], list), f"Example {i}: instructions is not a list"
            assert len(raw["ingredients"]) > 0, f"Example {i}: ingredients list is empty"
            assert len(raw["instructions"]) >= 2, (
                f"Example {i}: instructions has {len(raw['instructions'])} steps, expected >= 2"
            )

    def test_title_is_nonempty_string(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            assert isinstance(raw["title"], str), f"Example {i}: title is not a string"
            assert len(raw["title"].strip()) > 0, f"Example {i}: title is empty"


@pytest.mark.soft_gate
class TestRecipeImportHeuristic:
    """Layer 2: Heuristic checks (soft gate)."""

    def test_no_empty_instruction_steps(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            for j, step in enumerate(raw.get("instructions", [])):
                if not step or not step.strip():
                    failures.append(f"Example {i}: instruction step {j + 1} is empty")
        assert not failures, "Empty instruction check:\n" + "\n".join(failures)

    def test_total_time_is_valid_iso8601(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        iso_pattern = re.compile(r"^PT(\d+H)?(\d+M)?(\d+S)?$")
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            total_time = raw.get("total_time")
            if total_time and not iso_pattern.match(total_time):
                failures.append(f"Example {i}: total_time '{total_time}' is not valid ISO 8601 duration")
        assert not failures, "ISO 8601 duration check:\n" + "\n".join(failures)

    def test_no_empty_ingredients(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            for j, ing in enumerate(raw.get("ingredients", [])):
                if not ing or not ing.strip():
                    failures.append(f"Example {i}: ingredient {j + 1} is empty")
        assert not failures, "Empty ingredient check:\n" + "\n".join(failures)

    def test_dietary_flags_are_strings(
        self,
        eval_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        failures = []
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            for flag in raw.get("dietary_flags", []):
                if not isinstance(flag, str):
                    failures.append(f"Example {i}: dietary_flag {flag} is not a string")
        assert not failures, "Dietary flags type check:\n" + "\n".join(failures)


@pytest.mark.soft_gate
class TestRecipeImportJudge:
    """Layer 3: LLM-as-judge (soft gate)."""

    def test_judge_scores_above_threshold(
        self,
        eval_model: BaseChatModel,
        judge_model: BaseChatModel,
        recipe_import_dataset: list[dict[str, Any]],
    ) -> None:
        scores: list[int] = []
        for i, example in enumerate(recipe_import_dataset):
            content = _invoke_recipe_import(eval_model, example["input"]["html"], example_idx=i)
            raw = json.loads(content)
            score = judge_recipe_import(
                model=judge_model,
                html_snippet=example["input"]["html"],
                extracted_json=raw,
            )
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0
        assert avg_score >= 3.0, f"Average judge score {avg_score:.2f} below threshold 3.0"
