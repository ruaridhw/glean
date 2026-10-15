"""Scripted stand-ins for the two system boundaries normalisation talks to: the decisions endpoint and the LLM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from glean.catalogue.groups import GROUPS, Form, GroupId
from glean.decisions import ChoiceAnswer, Decision, NoulAnswer, Usage

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from glean.decisions import Question

NONE_OF_THESE = "none of these"


def _choice(name_to_probability: Mapping[str, float]) -> ChoiceAnswer:
    best = max(name_to_probability, key=lambda key: name_to_probability[key])
    return ChoiceAnswer(
        type="choice", choice=best, probabilities=dict(name_to_probability), confidence=name_to_probability[best]
    )


def decision(
    questions: Mapping[str, Question],
    *,
    match: Mapping[str, float] | None = None,
    group: GroupId = GroupId.OTHER,
    form: Form = Form.NOT_APPLICABLE,
    perishable: float = 0.1,
) -> Decision:
    """A Decision answering every question normalisation asks.

    `match` gives probabilities by option name; whatever is left over goes to "none of these".
    """
    match = dict(match or {})
    match[NONE_OF_THESE] = max(0.0, 1.0 - sum(match.values()))
    group_options = questions["ingredient_group"].criteria  # ty: ignore[unresolved-attribute]
    form_options = questions["form"].criteria  # ty: ignore[unresolved-attribute]
    answers: dict[str, Any] = {
        "match": _choice({key: match.get(key, 0.0) for key in questions["match"].criteria}),  # ty: ignore[unresolved-attribute]
        "ingredient_group": _choice({key: 1.0 if key == group.value else 0.0 for key in group_options}),
        "form": _choice({key: 1.0 if key == form.value else 0.0 for key in form_options}),
        "perishable": NoulAnswer(type="noul", noul=perishable),
    }
    return Decision(
        id="dec-test",
        model="typesafe/jev-1.14-20261014",
        provider="test",
        answers=answers,
        usage=Usage(input_tokens=1, output_tokens=0, cost=0.0),
    )


@dataclass
class FakeDecisions:
    """Answers `decide` from a per-name script; records every call."""

    script: Callable[[str, Mapping[str, Question]], Decision]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def decide(self, state: Mapping[str, Any], questions: Mapping[str, Question]) -> Decision:
        self.calls.append({"state": dict(state), "questions": dict(questions)})
        return self.script(state["name"], questions)


def all_groups() -> list[str]:
    return [group.value for group in GROUPS]


@dataclass
class FakeRouter:
    """Stands in for LLMRouter: `invoke(feature, schema, messages, **kwargs)` answers from `script`; records calls."""

    script: Callable[[Any, list[str]], Any] | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def invoke(self, feature: Any, schema: type, messages: Any, **kwargs: Any) -> Any:
        self.calls.append({"feature": feature, "schema": schema, "messages": messages, "kwargs": kwargs})
        if self.script is None:
            raise AssertionError("unexpected LLM call")
        return self.script(schema, messages)
