"""The V7 graph: `prepare -> plan <-> act -> finalise`, driven by a scripted model (spec §6.2, §10 V7).

Seam: `agent.start`, the agent module's interface, with the model faked at `LLMRouter.invoke` and the corpus a
synthetic filesystem store. A script of `PlanStep` answers drives the act loop, so these pin what the graph does
with each answer -- the tools it runs, the progress lines it writes, the budget, the fallback, drift, crash
recovery and cancel -- without a provider. They miss what a real model chooses, which the corpus eval measures.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from glean.agent import runtime, start
from glean.agent.actions import PlanStep
from glean.agent.checkpoint import in_memory_checkpointer
from glean.agent.control import AGENT_RUN_BUDGET_SECONDS
from glean.agent.deps import AgentDeps
from glean.agent.graph import FINALISE_LINE, MAX_INVALID_ACTIONS, MAX_TOOL_CALLS, PLAN_LINE, PREPARE_LINE
from glean.meal_plan.schemas import CompressedPantryItem, CookedHistoryItem, MealPlanRequest
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe
from glean.sessions.models import AgentSession, SessionStatus
from glean.sessions.store import MAX_LEASE_SECONDS, WORKER_TIMEOUT_SECONDS, InMemorySessionStore

NOW = datetime(2026, 10, 25, 12, tzinfo=UTC)
NOTE = "PRIVATE-NOTE-the-kids-hated-it"
KOREAN_ID = "rec_korean"

type Step = dict[str, Any] | BaseException | Callable[[dict[str, Any]], dict[str, Any]]


class Clock:
    def __init__(self) -> None:
        self.now = NOW
        self.seconds = 0.0

    def wall(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.seconds

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)
        self.seconds += seconds


class Metrics:
    def __init__(self) -> None:
        self.recorded: dict[str, list[Any]] = {}

    def add_metric(self, *, name: str, unit: object, value: object) -> None:
        self.recorded.setdefault(name, []).append(value)


class ScriptedModel:
    """The model at its boundary: answers a script of PlanSteps, one per call, and records what it was shown."""

    def __init__(self, *steps: Step) -> None:
        self.steps = list(steps)
        self.users: list[str] = []

    def invoke(self, _feature: object, schema: type, *, user: str, **_kwargs: object) -> Any:
        assert schema is PlanStep
        self.users.append(user)
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            step = step(json.loads(user))
        return PlanStep.model_validate(step)

    def model_id_for(self, _feature: object, **_kwargs: object) -> str:
        return "scripted/model"

    @property
    def calls(self) -> int:
        return len(self.users)


def call(name: str, **args: Any) -> dict[str, Any]:
    return {"action": {"kind": "call_tool", "call": {"name": name, **args}}}


def propose_first(context: dict[str, Any]) -> dict[str, Any]:
    """Propose the scorer's first candidate week, as a model that changes nothing would."""
    meals = context["candidate_weeks"][0]["meals"]
    return _proposal(meals, chosen_week=0)


def propose_found(context: dict[str, Any]) -> dict[str, Any]:
    """Swap the found Korean recipe into the scorer's first week, as a model acting on a search would."""
    found = next(
        row
        for result in context["tool_results"]
        if "call" in result
        for row in result["result"].get("recipes", [])
        if row["external_id"] == KOREAN_ID
    )
    meals = [m for m in context["candidate_weeks"][0]["meals"] if m["external_id"] != KOREAN_ID][:1]
    return _proposal([{"external_id": found["external_id"], "title": found["title"]}, *meals], chosen_week=None)


def _proposal(meals: list[dict[str, Any]], *, chosen_week: int | None) -> dict[str, Any]:
    return {
        "action": {
            "kind": "propose",
            "proposal": {
                "week_summary": "A scripted week.",
                "chosen_week": chosen_week,
                "suggestions": [
                    {"external_id": meal["external_id"], "title": meal["title"], "reason": "Scripted."}
                    for meal in meals
                ],
            },
        }
    }


def _corpus(root: Any) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(root))
    dishes = [(KOREAN_ID, "Bibimbap bowl", "korean", "gochujang")]
    dishes += [(f"rec_{index:02d}", f"Synthetic dish {index:02d}", "british", f"thing{index}") for index in range(40)]
    for external_id, title, cuisine, ingredient in dishes:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                cuisine=cuisine,
                total_time_mins=30,
                ingredients=[
                    StoredIngredient(canonical_name=ingredient, quantity=1, unit="each"),
                    *(
                        []
                        if external_id == KOREAN_ID
                        else [StoredIngredient(canonical_name="onion", quantity=1, unit="each")]
                    ),
                ],
            )
        )
    return corpus


def _request() -> MealPlanRequest:
    return MealPlanRequest(
        source="corpus",
        # Every dish but the Korean one uses the onion, so the sampler's 25 come from those 40 and the Korean
        # dish is offered only if the agent goes looking for it.
        pantry=[CompressedPantryItem(id=1, name="onion", quantity=1, unit="each", urgency_score=0.5)],
        purchase_tolerance=0.3,
        meals_per_week=2,
        dietary_flags=[],
        max_active_time_mins=None,
        # V8's notes ride the request; nothing may carry one to the model.
        cooked_history=[
            CookedHistoryItem(
                recipe_id="rec_00",
                title="Synthetic dish 00",
                cooked_at=NOW - timedelta(days=90),
                rating="up",
                note=NOTE,
            )
        ],
    )


def _session() -> AgentSession:
    return AgentSession(session_id="sess-1", user_sub="user-a", request=_request())


class Run:
    """One session's store, clock and deps, so a test can start it, crash it and start it again."""

    def __init__(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        self.clock = Clock()
        self.sessions = InMemorySessionStore(clock=self.clock.wall)
        self.sessions.create(_session(), now=self.clock.now)
        self.checkpointer = in_memory_checkpointer()
        self.metrics = Metrics()
        self.root = tmp_path
        _corpus(tmp_path)
        monkeypatch.setattr(runtime, "metrics", self.metrics)

    def deps(self, model: ScriptedModel) -> AgentDeps:
        return AgentDeps(
            sessions=self.sessions,
            checkpointer=self.checkpointer,
            llm_router=model,  # ty: ignore[invalid-argument-type]
            corpus_factory=lambda: RecipeCorpusStore(FilesystemBlobStore(self.root)),
            clock=self.clock.wall,
            monotonic=self.clock.monotonic,
            remaining_seconds=lambda: float(WORKER_TIMEOUT_SECONDS),
        )

    def start(self, model: ScriptedModel) -> bool:
        return start(_session(), self.deps(model))

    @property
    def record(self) -> Any:
        record = self.sessions.get("user-a", "sess-1")
        assert record is not None
        return record

    def metric(self, name: str) -> list[Any]:
        return self.metrics.recorded.get(name, [])


@pytest.fixture
def run(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Run:
    return Run(tmp_path, monkeypatch)


class TestNextAction:
    def test_each_action_parses_into_its_typed_member(self) -> None:
        tool = PlanStep.model_validate(call("score_meal_plan", recipe_ids=["a", "b"]))
        proposal = PlanStep.model_validate(_proposal([{"external_id": "a", "title": "A"}], chosen_week=0))

        assert tool.action.kind == "call_tool"
        assert tool.action.call.recipe_ids == ["a", "b"]  # ty: ignore[unresolved-attribute]
        assert proposal.action.kind == "propose"

    @pytest.mark.parametrize(
        "answer",
        [
            call("delete_everything"),
            call("get_eligible_recipes", filter={"include": [{"field": "title", "op": "in", "values": ["x"]}]}),
            call("get_eligible_recipes", filter={"sql": "DROP TABLE recipes"}),
            {"action": {"kind": "ask_household", "question": "Fish?"}},
        ],
    )
    def test_anything_outside_the_union_or_the_allowlist_is_refused(self, answer: dict[str, Any]) -> None:
        with pytest.raises(ValueError, match="validation error"):
            PlanStep.model_validate(answer)


class TestActLoop:
    def test_the_agent_finds_scores_and_proposes_a_recipe_it_was_not_offered(self, run: Run) -> None:
        model = ScriptedModel(
            call("get_eligible_recipes", filter={"text": "korean", "limit": 10}),
            lambda context: call(
                "score_meal_plan", recipe_ids=[KOREAN_ID, context["candidate_weeks"][0]["meals"][1]["external_id"]]
            ),
            propose_found,
        )

        assert run.start(model) is True

        # The sampler offers 25 of the 40 dishes that use the onion; the Korean one is not among them.
        offered = [candidate["external_id"] for candidate in json.loads(model.users[0])["candidates"]]
        assert KOREAN_ID not in offered
        record = run.record
        assert record.status is SessionStatus.DONE
        assert record.progress == [
            PREPARE_LINE,
            PLAN_LINE,
            "Looking for something korean",
            "Balancing proteins across the week",
            FINALISE_LINE,
        ]
        assert record.result.degraded is False
        assert KOREAN_ID in [suggestion.external_id for suggestion in record.result.suggestions]
        # The model saw each tool's result on its next turn.
        last = json.loads(model.users[-1])
        assert [result["call"]["name"] for result in last["tool_results"]] == [
            "get_eligible_recipes",
            "score_meal_plan",
        ]
        assert "week" in last["tool_results"][1]["result"]
        assert last["tool_calls_left"] == MAX_TOOL_CALLS - 2
        assert run.metric("SessionToolCalls") == [2]
        assert run.metric("SessionInvalidActions") == [0]

    def test_a_filter_that_tries_to_widen_comes_back_as_an_error_the_model_reads(self, run: Run) -> None:
        model = ScriptedModel(call("get_eligible_recipes", filter={"limit": 500}), propose_first)

        run.start(model)

        result = json.loads(model.users[-1])["tool_results"][0]["result"]
        assert "limit must be between 1 and 120" in result["error"]
        assert run.record.status is SessionStatus.DONE
        assert run.record.result.degraded is False

    def test_an_id_the_week_may_not_use_cannot_be_scored(self, run: Run) -> None:
        model = ScriptedModel(call("score_meal_plan", recipe_ids=["rec_invented"]), propose_first)

        run.start(model)

        result = json.loads(model.users[-1])["tool_results"][0]["result"]
        assert "not recipes you may plan" in result["error"]


class TestInvalidActions:
    def test_an_unparseable_answer_is_counted_and_asked_again(self, run: Run) -> None:
        model = ScriptedModel(ValueError("not a NextAction"), propose_first)

        run.start(model)

        assert run.record.status is SessionStatus.DONE
        assert run.record.result.degraded is False
        assert "not a valid action" in json.loads(model.users[-1])["tool_results"][0]["error"]
        assert run.metric("SessionInvalidActions") == [1]

    def test_too_many_unparseable_answers_end_in_the_scorers_week(self, run: Run) -> None:
        model = ScriptedModel(*[ValueError("still not one")] * (MAX_INVALID_ACTIONS + 1))

        run.start(model)

        assert run.record.status is SessionStatus.DONE
        assert run.record.result.degraded is True
        assert model.calls == MAX_INVALID_ACTIONS + 1
        assert run.metric("SessionInvalidActions") == [MAX_INVALID_ACTIONS + 1]


class TestBudget:
    def test_a_ninth_tool_call_ends_in_the_scorers_week(self, run: Run) -> None:
        model = ScriptedModel(*[call("get_recipes", ids=["rec_01"])] * (MAX_TOOL_CALLS + 1))

        run.start(model)

        record = run.record
        assert record.status is SessionStatus.DONE
        assert record.result.degraded is True
        assert record.progress.count("Reading the recipes more closely") == MAX_TOOL_CALLS
        assert run.metric("SessionToolCalls") == [MAX_TOOL_CALLS]
        assert run.metric("SessionsDegraded") == [1]

    def test_spending_the_90_seconds_mid_loop_ends_in_the_scorers_week(self, run: Run) -> None:
        def slow(_context: dict[str, Any]) -> dict[str, Any]:
            run.clock.advance(AGENT_RUN_BUDGET_SECONDS + 1)
            return call("get_recipes", ids=["rec_01"])

        model = ScriptedModel(call("get_recipes", ids=["rec_01"]), slow)

        run.start(model)

        record = run.record
        assert record.status is SessionStatus.DONE
        assert record.error is None
        assert record.result.degraded is True
        # The first call ran; the one asked for after the deadline did not.
        assert record.progress.count("Reading the recipes more closely") == 1

    def test_a_provider_error_mid_loop_is_the_scorers_week_not_model_error(self, run: Run) -> None:
        model = ScriptedModel(call("get_recipes", ids=["rec_01"]), RuntimeError("provider fell over"))

        run.start(model)

        assert run.record.status is SessionStatus.DONE
        assert run.record.error is None
        assert run.record.result.degraded is True


class TestDrift:
    def test_the_chosen_week_is_rescored_and_its_drift_recorded(
        self, run: Run, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO):
            run.start(ScriptedModel(propose_first))

        # The scorer's own best week: no shortfall at all.
        assert run.metric("SessionDrift") == [0.0]
        finished = next(r for r in caplog.records if r.getMessage() == "agent session finished")
        assert finished.drift_fraction == 0.0  # ty: ignore[unresolved-attribute]
        assert finished.drift_within_15_percent is True  # ty: ignore[unresolved-attribute]


class TestRecovery:
    def test_a_crash_mid_loop_resumes_from_the_checkpoint_without_repeating_finished_tool_calls(self, run: Run) -> None:
        class ProcessDied(BaseException):
            """A killed Lambda, from inside Python: nothing catches it."""

        dead = ScriptedModel(
            call("get_eligible_recipes", filter={"text": "korean"}),
            call("get_recipes", ids=[KOREAN_ID]),
            ProcessDied(),
        )
        with pytest.raises(ProcessDied):
            run.start(dead)
        assert run.record.status is SessionStatus.RUNNING

        run.clock.advance(MAX_LEASE_SECONDS + 10)
        resumed = ScriptedModel(propose_found)
        assert run.start(resumed) is True

        record = run.record
        assert record.status is SessionStatus.DONE
        assert record.progress.count("Looking for something korean") == 1
        assert record.progress.count("Reading the recipes more closely") == 1
        assert record.progress.count(PREPARE_LINE) == 1
        # The resumed run asked the model once, and it already held both tool results.
        assert resumed.calls == 1
        assert len(json.loads(resumed.users[0])["tool_results"]) == 2
        assert KOREAN_ID in [suggestion.external_id for suggestion in record.result.suggestions]
        assert run.metric("SessionToolCalls") == [2]


class TestCancel:
    def test_a_cancel_between_steps_stops_the_run_before_its_tool(self, run: Run) -> None:
        def cancels(_context: dict[str, Any]) -> dict[str, Any]:
            run.sessions.cancel("user-a", "sess-1")
            return call("get_eligible_recipes", filter={"text": "korean"})

        model = ScriptedModel(cancels)

        run.start(model)

        record = run.record
        assert record.status is SessionStatus.CANCELLED
        assert record.result is None
        assert "Looking for something korean" not in record.progress
        assert run.metric("SessionsCancelled") == [1]


class TestFreeText:
    def test_cooked_history_notes_never_reach_the_model(self, run: Run) -> None:
        model = ScriptedModel(
            call("get_eligible_recipes", filter={}),
            call("get_recipes", ids=["rec_00"], detail="full"),
            propose_first,
        )

        run.start(model)

        assert model.calls == 3
        assert all(NOTE not in user for user in model.users)
