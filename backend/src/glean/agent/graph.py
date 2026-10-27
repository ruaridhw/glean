"""The agent graph: `prepare -> plan <-> act -> finalise`, the agent working the week (spec §6.2, V7, V11).

- **prepare** runs `meal_plan.pipeline.prepare`, which samples the candidates and has the scorer build two
  candidate weeks with the week's chips, so the model starts with a balanced week in hand. The week's note was
  screened before the graph was invoked (`runtime`): the state holds only the screen's `feedback`, and only a
  note that passed reaches the model, as data.
- **plan** is the only LLM node. It returns one typed `NextAction` through structured output (ADR 0012):
  `call_tool`, `ask_household` or `propose`. An answer that does not parse, or that is refused (a second
  question, or one with nothing to tap), is counted and the model is asked again, up to `MAX_INVALID_ACTIONS`
  times; a provider failure ends the loop.
- **act** runs the chosen tool through its adapter, writes the tool's progress line first, and appends a
  compact result for the next `plan` turn. Recipes a tool found widen what the week may use. For the
  household's question it calls LangGraph's `interrupt()` instead: the checkpoint holds the run, the runtime
  parks the session as `waiting_for_user`, and the answer or the skip resumes `act` from the top with
  `Command(resume=...)`, so nothing before the interrupt in that node may have an effect. The answer reaches
  the next turn like a tool result, under `data`: the household's words are data, never instructions.
- **finalise** validates the proposal exactly as the sync route does (ids offered or found, nothing already
  planned, the count), re-scores the chosen week against the scorer's best and records the drift, and writes
  the proposal.

**The budget is in the state.** At most `MAX_TOOL_CALLS` tool calls, at most `MAX_QUESTIONS` question, and the
session's 90 s of working time (`RunGuard`; the seconds spent before the question are `working_seconds`, so the
household's thinking time is not counted). When
either is spent, or the model or a tool errors, `finalise` writes the degraded week instead: the scorer's best
week with template reasons, `degraded: true`. Once `prepare` has run there is always such a week, so from then
on a run never ends `model_error`.

**A swap is a second way in** (V10, spec §6.2 "Swap"). A finished session's thread is invoked again with a
`swap` input, and START routes it to `swap_start -> swap_plan <-> act -> swap_finalise`: the note arrives
already screened (the route screens it before anything stores it) and reaches the model only as the
`swap_note` field; the other slots are locked; the model proposes one replacement (`ProposeReplacement`)
within `MAX_SWAP_TOOL_CALLS`; and `swap_finalise` keeps it only if the week may use it, else takes the
scorer's best replacement. The swap's outcome is `swap_outcome`, keyed by its id, so a crashed swap resumes or
republishes like a crashed run.

The graph is built per run, closing over the deps and the guard, and is checkpointed under the session id as
its thread after every node, so a crashed run resumes at the node it died in and no finished tool call runs
again. Every field in `PlanState` is JSON, so a checkpoint is just data.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from langgraph.graph import END, START, StateGraph  # noqa: TID251 - this module owns LangGraph
from langgraph.types import interrupt  # noqa: TID251

from glean.agent import adapters
from glean.agent.actions import (
    TOOL_CALL,
    AskHousehold,
    CallTool,
    PlanStep,
    Propose,
    ProposeReplacement,
    SwapStep,
)
from glean.agent.control import BudgetSpent
from glean.agent.errors import AgentError, model_error_for
from glean.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    SWAP_SYSTEM_PROMPT,
    bounded_transcript,
    swap_user_message,
    user_message,
)
from glean.llm import Feature
from glean.meal_plan import pipeline, tools
from glean.meal_plan.feedback import ScreenedFeedback
from glean.meal_plan.household import ScreenedProfile
from glean.meal_plan.schemas import (
    CorpusMealPlanAlternative,
    CorpusMealPlanResponse,
    MealPlanRequest,
    MealPlanResult,
)
from glean.observability import logger
from glean.sessions.models import (
    MAX_OPTION_CHARS,
    MAX_OPTIONS,
    MAX_QUESTION_CHARS,
    HouseholdReply,
    PendingQuestion,
    SessionError,
    SessionErrorCode,
    SwapState,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from langgraph.graph.state import CompiledStateGraph  # noqa: TID251
    from pydantic import BaseModel

    from glean.agent.control import RunGuard
    from glean.agent.deps import AgentDeps
    from glean.recipes.corpus import RecipeCorpusStore

# Spec §6.2's agent budget: at most 8 tool calls and 1 question in one session.
MAX_TOOL_CALLS = 8
MAX_QUESTIONS = 1
# A swap looks for one meal, not a week: a search for what the note asks, a closer look, a score.
MAX_SWAP_TOOL_CALLS = 3
# Answers that do not parse as a NextAction, asked again before the run gives up on the model.
MAX_INVALID_ACTIONS = 2
# How much of a parse error is shown back to the model: enough to correct, not a wall of schema.
_ERROR_CHARS = 300

PREPARE_LINE = "Reading your pantry and the recipes we know"
PLAN_LINE = "Choosing this week's dinners"
FINALISE_LINE = "Checking the week against what you can cook"
# A swap's own lines, which the card being swapped shows in place (V10 direction A).
SWAP_NOTE_LINE = "Reading your note"
SWAP_LINE = "Finding another dinner"
SWAP_FINALISE_LINE = "Checking it fits the week"


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
    # The request without the week's raw note (`feedback.without_note`); the note's screened form is `feedback`.
    # Likewise without the profile's prose (`household.without_profile_text`), whose screened form is `profile`.
    request: dict[str, Any]
    feedback: dict[str, Any] | None
    profile: dict[str, Any] | None
    prepared: dict[str, Any] | None
    # The run so far, as the model reads it: each tool call with its compact result, and any answer of the
    # model's that did not parse.
    transcript: list[dict[str, Any]]
    # The tool call `plan` chose and `act` has not yet run.
    pending: dict[str, Any] | None
    # The household question `plan` chose (a bounded `PendingQuestion`), until `act` hears the answer.
    question: dict[str, Any] | None
    questions_asked: int
    # The session's working seconds when it asked its question; the resumed attempt's budget starts there.
    working_seconds: float
    proposal: dict[str, Any] | None
    tool_calls: int
    invalid_actions: int
    degraded_reason: str | None
    result: dict[str, Any] | None
    session_metrics: dict[str, Any] | None
    # A swap (V10): what the runtime asked for -- the slot, its position, the screened note, the locked meals,
    # the ids it may not use and the proposal it changes -- and what the swap made of it. The note is already
    # what the route's screen passed; `swap_note` is the one field that puts it in front of the model.
    swap: dict[str, Any] | None
    swap_note: str | None
    swap_pick: dict[str, Any] | None
    swap_outcome: dict[str, Any] | None


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
    graph.add_node("swap_start", nodes.swap_start)
    graph.add_node("swap_plan", nodes.swap_plan)
    graph.add_node("swap_finalise", nodes.swap_finalise)
    graph.add_conditional_edges(START, _route_start, ["prepare", "swap_start"])
    graph.add_edge("prepare", "plan")
    graph.add_conditional_edges("plan", _after_plan, ["act", "finalise"])
    graph.add_conditional_edges("act", _after_act, ["plan", "swap_plan"])
    graph.add_edge("finalise", END)
    graph.add_edge("swap_start", "swap_plan")
    graph.add_conditional_edges("swap_plan", _after_plan, ["act", "swap_finalise"])
    graph.add_edge("swap_finalise", END)
    # ty widens the compiled graph's parameters away from the annotation above.
    return graph.compile(checkpointer=deps.checkpointer)  # ty: ignore[invalid-return-type]


class _Nodes:
    """The four nodes of one run, closing over its deps and its guard."""

    def __init__(self, deps: AgentDeps, guard: RunGuard) -> None:
        self._deps = deps
        self._guard = guard
        # The corpus and the tools' view of it, read once per run at the first tool call (N6): every summary,
        # answer and decision, which no tool call changes. Not checkpointed; a resumed run reads them again.
        self._corpus: RecipeCorpusStore | None = None
        self._context: tools.EligibilityContext | None = None

    def _tools(self, state: PlanState) -> tuple[RecipeCorpusStore, tools.EligibilityContext]:
        if self._corpus is None or self._context is None:
            self._corpus = self._deps.corpus_factory()
            self._context = pipeline.tool_context(
                MealPlanRequest.model_validate(state["request"]),
                corpus=self._corpus,
                now=self._deps.clock(),
                seed=adapters.session_seed(state["session_id"]),
            )
        return self._corpus, self._context

    def prepare(self, state: PlanState) -> PlanState:
        # A budget spent here is `model_error`: there is no scorer week to fall back to yet.
        self._guard.step(PREPARE_LINE)
        prepared = self._prepared(state)
        if not prepared.has_candidates:
            # Nothing passes the dietary decisions, the time cap and the recency floor: the app says
            # "No recipes fit your diet and time limit" and sends the household to Settings.
            raise AgentError(SessionError(code=SessionErrorCode.NO_ELIGIBLE_RECIPES))
        return {"prepared": prepared.model_dump(mode="json"), "transcript": [], "tool_calls": 0, "invalid_actions": 0}

    def _prepared(self, state: PlanState) -> pipeline.PreparedPlan:
        return pipeline.prepare(
            MealPlanRequest.model_validate(state["request"]),
            # A state without `feedback` (none was screened) plans with the chips and no note.
            feedback=None if state.get("feedback") is None else ScreenedFeedback.model_validate(state["feedback"]),
            # Likewise a state without `profile` plans with the profile's enum fields and none of its words.
            profile=None if state.get("profile") is None else ScreenedProfile.model_validate(state["profile"]),
            corpus=self._deps.corpus_factory(),
            # The session id seeds the sampler, so a resumed run (or a swap whose checkpoint expired) is offered
            # the same candidates.
            rng=random.Random(state["session_id"]),  # noqa: S311 - varies recipe sampling, not security
            now=self._deps.clock(),
        )

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
        calls_left = max(MAX_TOOL_CALLS - tool_calls, 0)
        asked = state.get("questions_asked", 0)
        step = self._ask(
            PlanStep,
            AGENT_SYSTEM_PROMPT,
            lambda results: user_message(
                prepared.user,
                tool_results=results,
                tool_calls_left=calls_left,
                questions_left=max(MAX_QUESTIONS - asked, 0),
            ),
            transcript,
            invalid=state.get("invalid_actions", 0),
            refuse=lambda action: _refused(action, asked=asked),
        )
        if not isinstance(step, _Answer):
            return step
        action = step.action
        update: PlanState = {"invalid_actions": step.invalid, "transcript": transcript}
        if isinstance(action, AskHousehold):
            logger.info("the agent asked the household a question", extra={"tool_calls": tool_calls})
            return {
                **update,
                "pending": None,
                "question": _bounded(action).model_dump(mode="json"),
                "questions_asked": asked + 1,
                "working_seconds": self._guard.spent(),
            }
        if isinstance(action, Propose):
            return {**update, "proposal": action.proposal.model_dump(mode="json"), "pending": None}
        if not isinstance(action, CallTool):
            return _degrade(DegradedReason.INVALID_ACTIONS, **update)
        if tool_calls >= MAX_TOOL_CALLS:
            logger.warning("the agent asked for a tool after its last call", extra={"tool_calls": tool_calls})
            return _degrade(DegradedReason.TOOL_BUDGET, **update)
        return {**update, "pending": action.call.model_dump(mode="json")}

    def _ask(
        self,
        schema: type[PlanStep | SwapStep],
        system: str,
        user: Callable[[list[dict[str, Any]]], str],
        transcript: list[dict[str, Any]],
        *,
        invalid: int,
        refuse: Callable[[Any], str | None] | None = None,
    ) -> _Answer | PlanState:
        """Ask the model for its next action, again after an answer that does not parse or is refused; or give up.

        `transcript` gains a line per unparseable answer, and per answer *refuse* turns down (the week's plan
        refuses a second question, or one with nothing to tap), so the model sees what it got wrong. A provider
        failure is not retried: the scorer's week is a better use of what is left of the budget than a second wait.
        """
        while True:
            try:
                # The one blocking call: it may use what is left of the budget, never more.
                step: BaseModel = self._deps.llm_router.invoke(
                    Feature.MEAL_PLAN_GENERATION,
                    schema,
                    system=system,
                    user=user(transcript),
                    timeout_ms=self._guard.remaining_ms(),
                )
            except ValueError as exc:
                # The answer was not a NextAction (pydantic's and the parser's errors are both ValueErrors).
                error = f"Your last answer was not a valid action: {str(exc)[:_ERROR_CHARS]}"
            except Exception as exc:  # a provider failure: the scorer's week, never a failed session
                reason = model_error_for(exc).code.value
                logger.exception("the model call failed; writing the scorer's week", extra={"reason": reason})
                return _degrade(reason, invalid_actions=invalid, transcript=transcript)
            else:
                refusal = None if refuse is None else refuse(step.action)
                if refusal is None:
                    return _Answer(step.action, invalid)
                error = refusal
            invalid += 1
            logger.warning("the model's answer was not a valid action", extra={"invalid_actions": invalid})
            if self._guard.remaining_ms() <= 0:
                # The time ran out, whatever the answer was: a spent budget, as at any other step.
                return _degrade(DegradedReason.TIME_BUDGET, invalid_actions=invalid, transcript=transcript)
            if invalid > MAX_INVALID_ACTIONS:
                return _degrade(DegradedReason.INVALID_ACTIONS, invalid_actions=invalid, transcript=transcript)
            transcript.append({"error": error})

    def act(self, state: PlanState) -> PlanState:
        if state.get("question"):
            return _hear(state)
        call = TOOL_CALL.validate_python(state["pending"])
        try:
            # Written before the tool runs: a cancel refuses it, so no tool runs after the household cancels.
            self._guard.step(adapters.progress_line(call))
        except BudgetSpent:
            return _degrade(DegradedReason.TIME_BUDGET)
        try:
            corpus, context = self._tools(state)
            outcome = adapters.run_tool(
                call,
                prepared=pipeline.PreparedPlan.model_validate(state["prepared"]),
                request=MealPlanRequest.model_validate(state["request"]),
                corpus=corpus,
                now=context.now,
                session_id=state["session_id"],
                context=context,
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
            "transcript": bounded_transcript(
                [*(state.get("transcript") or []), _entry(call.model_dump(mode="json"), outcome)]
            ),
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
            # and the evals see it. The household sees an ordinary proposal (spec §6.5). An agent stopped for
            # asking one tool too many keeps the best week it had scored, when that week is as good.
            week = _agents_best_week(state, prepared) if reason == DegradedReason.TOOL_BUDGET else None
            logger.warning("writing a fallback week", extra={"reason": reason, "agents_week": week is not None})
            result = pipeline.degraded(prepared, week=week)
        metrics = _session_metrics(state, prepared, result, reason)
        logger.info("agent session finished", extra=metrics)
        return {"result": result.model_dump(mode="json"), "session_metrics": metrics}

    def swap_start(self, state: PlanState) -> PlanState:
        """Start the swap's own loop with nothing spent. The note was screened before it was stored.

        If the checkpoint expired there is no prepared plan, so `prepare` re-runs on today's clock without the
        week's screened note (the thread no longer holds it); the request's chips still apply.
        """
        swap = state["swap"] or {}
        note = swap.get("note")
        self._guard.step(SWAP_NOTE_LINE if note else SWAP_LINE)
        prepared = state.get("prepared") or self._prepared(state).model_dump(mode="json")
        return {
            "prepared": prepared,
            "swap_note": note,
            "swap_pick": None,
            "swap_outcome": None,
            "transcript": [],
            "pending": None,
            "tool_calls": 0,
            "invalid_actions": 0,
            "degraded_reason": None,
        }

    def swap_plan(self, state: PlanState) -> PlanState:
        """Ask for one replacement, or a tool first; the same loop as `plan`, on a smaller budget."""
        if state.get("degraded_reason"):
            return {"pending": None}
        tool_calls = state.get("tool_calls", 0)
        transcript = list(state.get("transcript") or [])
        try:
            self._guard.step(None)
        except BudgetSpent:
            return _degrade(DegradedReason.TIME_BUDGET)
        prepared = pipeline.PreparedPlan.model_validate(state["prepared"])
        swap = _swap_context(state, prepared)
        calls_left = max(MAX_SWAP_TOOL_CALLS - tool_calls, 0)
        step = self._ask(
            SwapStep,
            SWAP_SYSTEM_PROMPT,
            lambda results: swap_user_message(
                prepared.user, swap=swap, tool_results=results, tool_calls_left=calls_left
            ),
            transcript,
            invalid=state.get("invalid_actions", 0),
        )
        if not isinstance(step, _Answer):
            return step
        action = step.action
        update: PlanState = {"invalid_actions": step.invalid, "transcript": transcript}
        if isinstance(action, ProposeReplacement):
            return {**update, "swap_pick": action.replacement.model_dump(mode="json"), "pending": None}
        if not isinstance(action, CallTool):
            return _degrade(DegradedReason.INVALID_ACTIONS, **update)
        if tool_calls >= MAX_SWAP_TOOL_CALLS:
            logger.warning("the agent asked for a tool after its last swap call", extra={"tool_calls": tool_calls})
            return _degrade(DegradedReason.TOOL_BUDGET, **update)
        return {**update, "pending": action.call.model_dump(mode="json")}

    def swap_finalise(self, state: PlanState) -> PlanState:
        """Keep the model's replacement if the week may use it, else the scorer's best; write the swap's outcome.

        Nothing here raises for an empty offer: no meal left to swap in leaves the proposal as it was.
        """
        self._guard.step(SWAP_FINALISE_LINE, budget=False)
        swap = state["swap"] or {}
        base = MealPlanResult.model_validate(swap["base"])
        position = swap["position"]
        prepared = pipeline.PreparedPlan.model_validate(state["prepared"])
        reason = state.get("degraded_reason")
        raw_pick = None if reason else state.get("swap_pick")
        pick = None if raw_pick is None else CorpusMealPlanAlternative.model_validate(raw_pick)
        chosen = None
        if position < len(base.suggestions):
            chosen = pipeline.replacement(
                prepared,
                pick,
                locked=list(swap.get("locked", [])),
                unavailable=set(swap.get("unavailable_ids", [])),
            )
        if chosen is None:
            logger.warning("nothing left to swap in; the proposal stays as it was", extra={"reason": reason})
            state_, result, degraded = SwapState.NO_REPLACEMENT, base, True
        else:
            suggestion, degraded = chosen
            state_, result = (
                SwapState.DONE,
                pipeline.with_replacement(
                    base, position, suggestion, taken={swap.get("slot", ""), *swap.get("week", [])}
                ),
            )
            if degraded and reason is None:
                reason = DegradedReason.NOTHING_KEPT
        logger.info(
            "agent swap finished",
            extra={
                "swap_id": swap.get("swap_id"),
                "state": state_.value,
                "degraded": degraded,
                "degraded_reason": reason,
                "tool_calls": state.get("tool_calls", 0),
            },
        )
        return {
            "swap_outcome": {
                "swap_id": swap.get("swap_id"),
                "state": state_.value,
                "result": result.model_dump(mode="json"),
                "degraded": degraded and state_ is SwapState.DONE,
                "degraded_reason": reason,
            }
        }


@dataclass(frozen=True)
class _Answer:
    """A parsed action, and how many answers before it did not parse."""

    action: CallTool | AskHousehold | Propose | ProposeReplacement
    invalid: int


def _entry(call: dict[str, Any], outcome: adapters.ToolOutcome) -> dict[str, Any]:
    """One transcript entry: the call, then its refusal as `error` or its output under `data`.

    `data` holds third-party recipe text, and the system prompt says everything under it is data, never an
    instruction, so the key is what marks it.
    """
    if "error" in outcome.result:
        return {"call": call, "error": outcome.result["error"]}
    return {"call": call, "data": outcome.result}


def _agents_best_week(state: PlanState, prepared: pipeline.PreparedPlan) -> list[str] | None:
    """The best week the agent scored before its tool budget ran out, if it is as good as the scorer's best.

    Every week a `score_meal_plan` or `create_candidate_meal_plans` result holds is a candidate, re-scored here
    from the facts rather than read from the rounded result. "As good" is spec §6.6's drift gate: within 15% of
    the scorer's best. Below that the agent's work was a detour, and the scorer's week is the better fallback.

    The agent's week must also be as long as the scorer's best. The drift gate alone cannot see a short week: in
    a pool where nothing scores, one dinner is "within 15%" of four, and the household would get one.
    """
    if not prepared.weeks:
        return None
    size = len(prepared.weeks[0].recipe_ids)
    weeks: list[list[str]] = []
    for entry in state.get("transcript") or []:
        data = entry.get("data") or {}
        if "week" in data:
            weeks.append(data["week"]["recipe_ids"])
        weeks.extend(week["recipe_ids"] for week in data.get("weeks", []))
    offered, excluded = set(prepared.offered_ids), set(prepared.excluded_ids)
    usable = [
        week
        for week in weeks
        if len(week) == size and len(set(week)) == len(week) and set(week) <= offered and not set(week) & excluded
    ]
    if not usable:
        return None
    gaps = [(pipeline.plan_drift(prepared, week), week) for week in usable]
    gap, best = min(((gap, week) for gap, week in gaps if gap is not None), key=lambda item: item[0].gap)
    return best if gap.within_15_percent else None


def _route_start(state: PlanState) -> str:
    """A thread invoked with a swap works that swap; anything else plans the week."""
    return "swap_start" if state.get("swap") else "prepare"


def _after_plan(state: PlanState) -> str:
    if state.get("pending") or state.get("question"):
        return "act"
    return "swap_finalise" if state.get("swap") else "finalise"


def _after_act(state: PlanState) -> str:
    return "swap_plan" if state.get("swap") else "plan"


def _refused(action: Any, *, asked: int) -> str | None:
    """Why a well-formed action may still not be taken, said to the model; None when it may."""
    if not isinstance(action, AskHousehold):
        return None
    if asked >= MAX_QUESTIONS:
        return "You have already asked your one question this session. Plan with what you know."
    if not action.question.strip():
        return "A question needs words: ask it in one short sentence, or plan with what you know."
    if not any(option.strip() for option in action.options):
        return "A question needs at least one option for the household to tap."
    return None


def _bounded(action: AskHousehold) -> PendingQuestion:
    """The question as the session item holds it: clipped, its options de-duplicated and capped."""
    options: list[str] = []
    for option in action.options:
        clipped = option.strip()[:MAX_OPTION_CHARS]
        if clipped and clipped not in options:
            options.append(clipped)
    return PendingQuestion(
        question=action.question.strip()[:MAX_QUESTION_CHARS],
        options=options[:MAX_OPTIONS],
        why=action.why.strip()[:MAX_QUESTION_CHARS],
    )


def _hear(state: PlanState) -> PlanState:
    """Park the run on the question, and on resume record the household's answer for the next `plan` turn.

    `interrupt` checkpoints and stops the run the first time; the runtime then parks the session. When the
    answer arrives as `Command(resume=reply)`, LangGraph runs this node again from the top and `interrupt`
    returns the reply instead. Nothing may happen before it, or it would happen twice.

    The answer joins the transcript as a tool result does, under `data`: the option and the screened note in
    their own typed fields, never as instructions, and a skip as `skipped: true` with neither.
    """
    question = state["question"]
    reply = HouseholdReply.model_validate(interrupt(question))
    answer = {
        "skipped": reply.skipped,
        "option": None if reply.skipped else reply.option,
        "note": None if reply.skipped else reply.note,
    }
    logger.info("the household answered", extra={"skipped": reply.skipped, "note_dropped": reply.note_dropped})
    return {
        "question": None,
        "transcript": bounded_transcript([*(state.get("transcript") or []), {"question": question, "data": answer}]),
    }


def _swap_context(state: PlanState, prepared: pipeline.PreparedPlan) -> dict[str, Any]:
    """The swap as the model reads it: the slot, what stays, what it may not use, and the screened note only."""
    swap = state["swap"] or {}

    def meal(external_id: str) -> dict[str, str]:
        return {"external_id": external_id, "title": prepared.titles.get(external_id, external_id)}

    return {
        "replacing": meal(swap.get("slot", "")),
        "locked_week": [meal(external_id) for external_id in swap.get("locked", [])],
        "unavailable_ids": swap.get("unavailable_ids", []),
        "swap_note": state.get("swap_note"),
    }


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
        "questions_asked": state.get("questions_asked", 0),
        "degraded": result.degraded,
        "degraded_reason": reason,
        "note_outcome": None if prepared.feedback.note_outcome is None else prepared.feedback.note_outcome.value,
        "drift_fraction": None if gap is None else round(gap.fraction, 4),
        "drift_within_15_percent": None if gap is None else gap.within_15_percent,
    }


def swap_outcome_of(state: Mapping[str, Any], swap_id: int) -> dict[str, Any] | None:
    """The outcome `swap_finalise` wrote for *swap_id*, or None if this state has not finished that swap."""
    outcome = state.get("swap_outcome")
    return outcome if outcome and outcome.get("swap_id") == swap_id else None


def result_of(state: Mapping[str, Any]) -> MealPlanResult:
    """The plan the `finalise` node wrote into the graph state."""
    return MealPlanResult.model_validate(state["result"])


def outcome_of(state: Mapping[str, Any]) -> MealPlanResult | PendingQuestion:
    """What a week's run ended with: the plan `finalise` wrote, or the question `act` interrupted it on."""
    interrupts = state.get("__interrupt__")
    if interrupts:
        return PendingQuestion.model_validate(interrupts[0].value)
    return result_of(state)


def session_metrics_of(state: Mapping[str, Any]) -> dict[str, Any]:
    """The session metrics `finalise` recorded; empty for a checkpoint written before V7."""
    return dict(state.get("session_metrics") or {})
