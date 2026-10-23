"""The V1 graph: `prepare -> plan -> finalise`, the three steps of `meal_plan.pipeline`.

V1 wraps today's pipeline, so the picks and the reason text are exactly what `POST /meal-plan`
returns for the same request and seed. V7 widens `plan` into `plan <-> act` with tools and a typed
`NextAction`; the shape below is deliberately the smallest graph that fills a session.

The graph is built per run, closing over the deps and the progress writer, and is checkpointed under
the session id as its thread. Every field in `PlanState` is JSON, so a checkpoint is just data.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph  # noqa: TID251 - this module owns LangGraph

from glean.agent.errors import AgentError, model_error_for
from glean.meal_plan import pipeline
from glean.meal_plan.schemas import CorpusMealPlanRecipe, MealPlanRequest, MealPlanResult
from glean.sessions.models import SessionError, SessionErrorCode

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langgraph.graph.state import CompiledStateGraph  # noqa: TID251

    from glean.agent.control import RunGuard
    from glean.agent.deps import AgentDeps


class PlanState(TypedDict, total=False):
    """The graph state. Everything here must survive a JSON round trip in the checkpointer."""

    session_id: str
    request: dict[str, Any]
    prepared: dict[str, Any] | None
    picks: list[dict[str, Any]]
    result: dict[str, Any] | None


def build_graph(
    deps: AgentDeps,
    *,
    guard: RunGuard,
) -> CompiledStateGraph:
    """Compile the three-node graph for one run, checkpointing under the session id.

    Every node opens with `control.step`, which spends the run's budget, renews its lease and writes its
    progress line, so a run that is out of time or no longer owns the session stops before the next step.
    """

    def prepare(state: PlanState) -> PlanState:
        guard.step("Reading your pantry and the recipes we know")
        prepared = pipeline.prepare(
            MealPlanRequest.model_validate(state["request"]),
            corpus=deps.corpus_factory(),
            # The session id seeds the sampler, so a resumed run offers the same candidates.
            rng=random.Random(state["session_id"]),  # noqa: S311 - varies recipe sampling, not security
            now=deps.clock(),
        )
        if not prepared.has_candidates:
            # Nothing passes the dietary decisions, the time cap and the recency floor: the app says
            # "No recipes fit your diet and time limit" and sends the household to Settings.
            raise AgentError(SessionError(code=SessionErrorCode.NO_ELIGIBLE_RECIPES))
        return {"prepared": prepared.model_dump(mode="json")}

    def plan(state: PlanState) -> PlanState:
        guard.step("Choosing this week's dinners")
        prepared = pipeline.PreparedPlan.model_validate(state["prepared"])
        try:
            # The one blocking call: it may use what is left of the budget, never more.
            picks = pipeline.choose(prepared, llm_router=deps.llm_router, timeout_ms=guard.remaining_ms())
        except Exception as exc:
            # The only LLM call in V1: a provider failure is the household's `model_error`, never a crash.
            raise AgentError(model_error_for(exc)) from exc
        return {"picks": [pick.model_dump(mode="json") for pick in picks]}

    def finalise(state: PlanState) -> PlanState:
        guard.step("Checking the week against what you can cook")
        prepared = pipeline.PreparedPlan.model_validate(state["prepared"])
        picks = [CorpusMealPlanRecipe.model_validate(pick) for pick in state.get("picks", [])]
        result = pipeline.finalise(prepared, picks)
        return {"result": result.model_dump(mode="json")}

    # ty cannot see that a TypedDict with optional keys is a TypedDictLike; LangGraph reads it as one.
    graph = StateGraph(PlanState)  # ty: ignore[invalid-argument-type]
    graph.add_node("prepare", prepare)
    graph.add_node("plan", plan)
    graph.add_node("finalise", finalise)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "plan")
    graph.add_edge("plan", "finalise")
    graph.add_edge("finalise", END)
    # ty widens the compiled graph's parameters away from the annotation above.
    return graph.compile(checkpointer=deps.checkpointer)  # ty: ignore[invalid-return-type]


def result_of(state: Mapping[str, Any]) -> MealPlanResult:
    """The plan the `finalise` node wrote into the graph state."""
    return MealPlanResult.model_validate(state["result"])
