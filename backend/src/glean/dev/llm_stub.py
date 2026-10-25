"""A stand-in meal-plan model for the local async stack.

`make start-backend-docker` must run a whole session without model credits and without hiding a bug
behind a fake that answers everything: this picks the first candidates it was offered, exactly as the
prompt's rules allow, and refuses any schema it was not written for. Only `glean.dev.worker_loop`
uses it, and only when `AGENT_LLM_STUB=1`.
"""

from __future__ import annotations

import json
from typing import Any

from glean.agent.actions import PlanStep, Propose
from glean.meal_plan.schemas import CorpusMealPlanRecipe, CorpusMealPlanResponse, ReasonKind


class StubMealPlanRouter:
    """In place of `LLMRouter` for the local queue consumer."""

    def invoke(self, _feature: object, schema: type, *, user: str, **_kwargs: object) -> Any:
        if schema is PlanStep:
            # The agent's `plan` node (V7): propose at once, the same week the sync route would get.
            return PlanStep(action=Propose(kind="propose", proposal=self._week(json.loads(user))))
        if schema is not CorpusMealPlanResponse:
            raise NotImplementedError(f"the local stub only plans from the corpus, not {schema.__name__}")
        return self._week(json.loads(user))

    @staticmethod
    def _week(context: dict[str, Any]) -> CorpusMealPlanResponse:
        return CorpusMealPlanResponse(
            week_summary="A week of quick dinners.",
            suggestions=[
                CorpusMealPlanRecipe(
                    external_id=candidate["external_id"],
                    title=candidate["title"],
                    reason="Uses what is already in the pantry.",
                    reason_kind=ReasonKind.URGENT_ITEM if candidate["urgent_pantry_items"] else ReasonKind.BALANCE,
                )
                for candidate in context["candidates"][: context["meals_per_week"]]
            ],
        )

    def model_id_for(self, _feature: object, **_kwargs: object) -> str:
        return "local/stub"
