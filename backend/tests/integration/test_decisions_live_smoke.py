"""One live call to Jev's decisions endpoint. Needs a real OPENROUTER_API_KEY in backend/.env.

Run with: uv run pytest tests/integration/test_decisions_live_smoke.py -v --no-cov
Set LANGSMITH_TRACING=true (and LANGSMITH_API_KEY) to see the call in LangSmith as `jev_decide`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import pytest
from pydantic import Field, TypeAdapter

from glean.decisions import ChoiceQuestion, DecisionClient, NoulQuestion, ScoreQuestion

if TYPE_CHECKING:
    from pydantic import SecretStr

pytestmark = pytest.mark.integration

_PROBE = json.loads((Path(__file__).parents[1] / "fixtures" / "jev" / "probe_request.json").read_text())
_QUESTION_SET = TypeAdapter(
    dict[str, Annotated[ChoiceQuestion | NoulQuestion | ScoreQuestion, Field(discriminator="type")]]
)


def test_jev_answers_all_three_question_types_with_the_pinned_model(openrouter_api_key: SecretStr) -> None:
    client = DecisionClient(api_key=openrouter_api_key, timeout_s=30.0)

    decision = client.decide(_PROBE["state"], _QUESTION_SET.validate_python(_PROBE["questions"]))

    assert re.fullmatch(r"typesafe/jev-1\.13(-\d{8})?", decision.model)
    # 0.63 on 2026-10-15: pine nuts aren't a UK legal tree-nut allergen,
    # so don't assert a side here (#125 sets the policy).
    assert 0.0 <= decision.noul("contains_nuts").noul <= 1.0
    assert decision.choice("ingredient_group").choice == "condiments"
    assert 0.0 <= decision.score("quality").score <= 4.0
    assert decision.usage.cost < 0.01
