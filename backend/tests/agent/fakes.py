"""What every fake model in these tests shares: answering the agent's `plan` node with a proposal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from glean.agent.actions import PlanStep, Propose

if TYPE_CHECKING:
    from glean.meal_plan.schemas import CorpusMealPlanResponse


def proposed(schema: type, response: CorpusMealPlanResponse) -> Any:
    """*response* as the answer *schema* asks for: a `propose` action for the agent, the week itself otherwise.

    The agent's `plan` node asks for a `PlanStep` (V7) and the sync route for the week; a fake that only ever
    proposes serves both, so a test that is not about the act loop does not have to script one.
    """
    if schema is PlanStep:
        return PlanStep(action=Propose(kind="propose", proposal=response))
    return response
