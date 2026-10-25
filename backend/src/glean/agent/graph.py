"""The V7 graph: `prepare -> plan <-> act -> finalise`, the agent working the week (spec §6.2).

- **prepare** is deterministic: `meal_plan.pipeline.prepare` samples the candidates and the scorer builds two
  candidate weeks, so the model starts with a balanced week in hand.
- **plan** is the only LLM node. It returns one typed `NextAction` through structured output (ADR 0012):
  `call_tool` or `propose`. An answer that does not parse is counted and the model is asked again, up to
  `MAX_INVALID_ACTIONS` times; a provider failure ends the loop.
- **act** runs the chosen tool through its adapter, writes the tool's progress line first, and appends a
  compact result for the next `plan` turn. Recipes a tool found widen what the week may use.
- **finalise** validates the proposal exactly as the sync route does (ids offered or found, nothing already
  planned, the count), re-scores the chosen week against the scorer's best and records the drift, and writes
  the proposal.

**The budget is in the state.** At most `MAX_TOOL_CALLS` tool calls, and the run's 90 s (`RunGuard`). When
either is spent, or the model or a tool errors, `finalise` writes the degraded week instead: the scorer's best
week with template reasons, `degraded: true`. Once `prepare` has run there is always such a week, so from then
on a run never ends `model_error`.

The graph is built per run, closing over the deps and the guard, and is checkpointed under the session id as
its thread after every node, so a crashed run resumes at the node it died in and no finished tool call runs
again. Every field in `PlanState` is JSON, so a checkpoint is just data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph  # noqa: TID251 - this module owns LangGraph

from glean.agent import adapters
from glean.agent.actions import TOOL_CALL, CallTool, PlanStep, Propose
from glean.agent.control import BudgetSpent
from glean.agent.errors import AgentError, model_error_for
from glean.agent.prompts import AGENT_SYSTEM_PROMPT, user_message
from glean.llm import Feature
from glean.meal_plan import pipeline
from glean.meal_plan.schemas import CorpusMealPlanResponse, MealPlanRequest, MealPlanResult
from glean.observability import logger
from glean.sessions.models import SessionError, SessionErrorCode

if TYPE_CHECKING:
    from collections.abc import Mapping

    from langgraph.graph.state import CompiledStateGraph  # noqa: TID251

    from glean.agent.control import RunGuard
    from glean.agent.deps import AgentDeps

# Spec §6.2's agent budget: at most 8 tool calls in one session.
MAX_TOOL_CALLS = 8
# Answers that do not parse as a NextAction, asked again before the run gives up on the model.
MAX_INVALID_ACTIONS = 2
# How much of a parse error is shown back to the model: enough to correct, not a wall of schema.
_ERROR_CHARS = 300

PREPARE_LINE = "Reading your pantry and the recipes we know"
PLAN_LINE = "Choosing this week's dinners"
FINALISE_LINE = "Checking the week against what you can cook"


class DegradedReason:
    """Why `finalise` wrote the scorer's week instead of the model's. Logged and counted, never shown."""

    TOOL_BUDGET = "tool_budget"
    TIME_BUDGET = "time_budget"
    INVALID_ACTIONS = "invalid_actions"
    MODEL_ERROR = "model_error"
    RATE_LIMITED = "rate_limited"
    TOOL_ERROR = "tool_error"
    NOTHING_KEPT = "nothing_kept"


class PlanState(TypedDict, total=False):
    """The graph state. Everything here must survive a JSON round trip in the checkpointer."""

    session_id: str
    request: dict[str, Any]
    prepared: dict[str, Any] | None
    # The run so far, as the model reads it: each tool call with its compact result, and any answer of the
    # model's that did not parse.
    transcript: list[dict[str, Any]]
    # The tool call `plan` chose and `act` has not yet run.
    pending: dict[str, Any] | None
    proposal: dict[str, Any] | None
    tool_calls: int
    invalid_actions: int
    degraded_reason: str | None
    result: dict[str, Any] | None
    session_metrics: dict[str, Any] | None


def build_graph(
    deps: AgentDeps,
    *,
    guard: RunGuard,
) -> CompiledStateGraph:
    """Compile the four-node graph for one run, checkpointing under the session id.

    Every node opens with `guard.step`, which spends the run's budget and, when it writes a progress line,
    checks the run still owns the session and has not been cancelled -- so a cancel lands between steps, and
    no tool runs after one.
    """
    nodes = _Nodes(deps, guard)
    # ty cannot see that a TypedDict with optional keys is a TypedDictLike; LangGraph reads it as one.
    graph = StateGraph(PlanState)  # ty: ignore[invalid-argument-type]
    graph.add_node("prepare", nodes.prepare)
    graph.add_node("plan", nodes.plan)
    graph.add_node("act", nodes.act)
    graph.add_node("finalise", nodes.finalise)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "plan")
    graph.add_conditional_edges("plan", _after_plan, ["act", "finalise"])
    graph.add_edge("act", "plan")
    graph.add_edge("finalise", END)
    # ty widens the compiled graph's parameters away from the annotation above.
    return graph.compile(checkpointer=deps.checkpointer)  # ty: ignore[invalid-return-type]


class _Nodes:
    """The four nodes of one run, closing over its deps and its guard."""

    def __init__(self, deps: AgentDeps, guard: RunGuard) -> None:
        self._deps = deps
        self._guard = guard

    def prepare(self, state: PlanState) -> PlanState:
        # A budget spent here is `model_error`: there is no scorer week to fall back to yet.
        self._guard.step(PREPARE_LINE)
        prepared = pipeline.prepare(
            MealPlanRequest.model_validate(state["request"]),
            corpus=self._deps.corpus_factory(),
            # The session id seeds the sampler, so a resumed run offers the same candidates.
            rng=random.Random(state["session_id"]),  # noqa: S311 - varies recipe sampling, not security
            now=self._deps.clock(),
        )
        if not prepared.has_candidates:
            # Nothing passes the dietary decisions, the time cap and the recency floor: the app says
            # "No recipes fit your diet and time limit" and sends the household to Settings.
            raise AgentError(SessionError(code=SessionErrorCode.NO_ELIGIBLE_RECIPES))
        return {"prepared": prepared.model_dump(mode="json"), "transcript": [], "tool_calls": 0, "invalid_actions": 0}

    def plan(self, state: PlanState) -> PlanState:
        if state.get("degraded_reason"):
            # `act` already gave up (the budget, or a tool error): straight on to `finalise`.
            return {"pending": None}
        tool_calls = state.get("tool_calls", 0)
        transcript = list(state.get("transcript") or [])
        try:
            # The first turn says what the agent is doing; later turns are followed by an `act` or `finalise`
            # line of their own, so they only spend the budget.
            self._guard.step(PLAN_LINE if tool_calls == 0 and not transcript else None)
        except BudgetSpent:
            return _degrade(DegradedReason.TIME_BUDGET)
        prepared = pipeline.PreparedPlan.model_validate(state["prepared"])
        step = self._ask(prepared, transcript, tool_calls=tool_calls, invalid=state.get("invalid_actions", 0))
        if not isinstance(step, _Answer):
            return step
        action = step.action
        update: PlanState = {"invalid_actions": step.invalid, "transcript": transcript}
        if not isinstance(action, CallTool):
            return {**update, "proposal": action.proposal.model_dump(mode="json"), "pending": None}
        if tool_calls >= MAX_TOOL_CALLS:
            logger.warning("the agent asked for a tool after its last call", extra={"tool_calls": tool_calls})
            return _degrade(DegradedReason.TOOL_BUDGET, **update)
        return {**update, "pending": action.call.model_dump(mode="json")}

    def _ask(
        self, prepared: pipeline.PreparedPlan, transcript: list[dict[str, Any]], *, tool_calls: int, invalid: int
    ) -> _Answer | PlanState:
        """Ask the model for its next action, again after an answer that does not parse; or give up.

        `transcript` gains a line per unparseable answer, so the model sees what it got wrong. A provider failure
        is not retried: the scorer's week is a better use of what is left of the budget than a second wait.
        """
        while True:
            try:
                # The one blocking call: it may use what is left of the budget, never more.
                step = self._deps.llm_router.invoke(
                    Feature.MEAL_PLAN_GENERATION,
                    PlanStep,
                    system=AGENT_SYSTEM_PROMPT,
                    user=user_message(
                        prepared.user, tool_results=transcript, tool_calls_left=max(MAX_TOOL_CALLS - tool_calls, 0)
                    ),
                    timeout_ms=self._guard.remaining_ms(),
                )
            except ValueError as exc:
                # The answer was not a NextAction (pydantic's and the parser's errors are both ValueErrors).
                invalid += 1
                error = str(exc)[:_ERROR_CHARS]
                logger.warning("the model's answer was not a valid action", extra={"invalid_actions": invalid})
                if invalid > MAX_INVALID_ACTIONS or self._guard.remaining_ms() <= 0:
                    return _degrade(DegradedReason.INVALID_ACTIONS, invalid_actions=invalid, transcript=transcript)
                transcript.append({"error": f"Your last answer was not a valid action: {error}"})
                continue
            except Exception as exc:  # a provider failure: the scorer's week, never a failed session
                reason = model_error_for(exc).code.value
                logger.exception("the model call failed; writing the scorer's week", extra={"reason": reason})
                return _degrade(reason, invalid_actions=invalid, transcript=transcript)
            return _Answer(step.action, invalid)

    def act(self, state: PlanState) -> PlanState:
        call = TOOL_CALL.validate_python(state["pending"])
        try:
            # Written before the tool runs: a cancel refuses it, so no tool runs after the household cancels.
            self._guard.step(adapters.progress_line(call))
        except BudgetSpent:
            return _degrade(DegradedReason.TIME_BUDGET)
        try:
            outcome = adapters.run_tool(
                call,
                prepared=pipeline.PreparedPlan.model_validate(state["prepared"]),
                request=MealPlanRequest.model_validate(state["request"]),
                corpus=self._deps.corpus_factory(),
                now=self._deps.clock(),
                session_id=state["session_id"],
            )
        except Exception:  # a bug in a tool, not a refusal (those are results): the scorer's week
            logger.exception("a tool call failed; writing the scorer's week", extra={"tool": call.name})
            return _degrade(DegradedReason.TOOL_ERROR)
        tool_calls = state.get("tool_calls", 0) + 1
        logger.info(
            "agent tool call",
            extra={"tool": call.name, "tool_calls": tool_calls, "error": outcome.result.get("error")},
        )
        return {
            "pending": None,
            "prepared": outcome.prepared.model_dump(mode="json"),
            "transcript": [*(state.get("transcript") or []), {"call": state["pending"], "result": outcome.result}],
            "tool_calls": tool_calls,
        }

    def finalise(self, state: PlanState) -> PlanState:
        # The degraded week is still worth writing after the budget is spent, so this step does not spend it.
        self._guard.step(FINALISE_LINE, budget=False)
        prepared = pipeline.PreparedPlan.model_validate(state["prepared"])
        reason = state.get("degraded_reason")
        result = None
        if reason is None:
            draft = CorpusMealPlanResponse.model_validate(state.get("proposal") or {"suggestions": []})
            result = pipeline.finalise(prepared, draft)
            if not result.suggestions:
                # The model's answer kept nothing (it invented ids, or named meals already in the plan).
                reason = DegradedReason.NOTHING_KEPT
                result = None
        if result is None:
            # Spec §6.2's fallback: the scorer's best week with template text, flagged degraded so the logs
            # and the evals see it. The household sees an ordinary proposal (spec §6.5).
            logger.warning("writing the scorer's best week", extra={"reason": reason})
            result = pipeline.degraded(prepared)
        metrics = _session_metrics(state, prepared, result, reason)
        logger.info("agent session finished", extra=metrics)
        return {"result": result.model_dump(mode="json"), "session_metrics": metrics}


@dataclass(frozen=True)
class _Answer:
    """A parsed NextAction, and how many answers before it did not parse."""

    action: CallTool | Propose
    invalid: int


def _after_plan(state: PlanState) -> str:
    return "act" if state.get("pending") else "finalise"


def _degrade(reason: str, **update: Any) -> PlanState:
    """End the loop: `finalise` writes the scorer's week and records why."""
    return {**update, "pending": None, "degraded_reason": reason}


def _session_metrics(
    state: PlanState, prepared: pipeline.PreparedPlan, result: MealPlanResult, reason: str | None
) -> dict[str, Any]:
    """Spec §6.6's session metrics for this run: tool calls, invalid answers, the fallback, and the drift."""
    chosen = [suggestion.external_id for suggestion in result.suggestions if suggestion.external_id]
    gap = pipeline.plan_drift(prepared, chosen)
    return {
        "tool_calls": state.get("tool_calls", 0),
        "invalid_actions": state.get("invalid_actions", 0),
        "degraded": result.degraded,
        "degraded_reason": reason,
        "drift_fraction": None if gap is None else round(gap.fraction, 4),
        "drift_within_15_percent": None if gap is None else gap.within_15_percent,
    }


def result_of(state: Mapping[str, Any]) -> MealPlanResult:
    """The plan the `finalise` node wrote into the graph state."""
    return MealPlanResult.model_validate(state["result"])


def session_metrics_of(state: Mapping[str, Any]) -> dict[str, Any]:
    """The session metrics `finalise` recorded; empty for a checkpoint written before V7."""
    return dict(state.get("session_metrics") or {})
