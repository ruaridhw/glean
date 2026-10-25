"""V10: a swap message resumes a finished session and replaces one meal (spec §6.2 "Swap").

Seam: `agent.start`, what the worker and the inline runner call for every queue delivery, after the store has
queued a swap with the note the route's screen passed (screening itself is pinned in `test_swap_api.py`). The
model is scripted at `LLMRouter.invoke` and the corpus is a synthetic filesystem store, so these pin the swap's
graph -- the screened note passed only as data, the other slots locked, planned meals never replaced, the
scorer's fallback, the lease and the checkpoint -- without a provider. They miss what a real model picks for a
note, which the eval measures.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from glean.agent import MessageNotSent, resume, start
from glean.agent.actions import PlanStep, SwapStep
from glean.agent.checkpoint import in_memory_checkpointer
from glean.agent.deps import AgentDeps
from glean.agent.graph import MAX_SWAP_TOOL_CALLS, SWAP_FINALISE_LINE, SWAP_LINE, SWAP_NOTE_LINE
from glean.meal_plan.pipeline import TEMPLATE_SWAP_REASON
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.sessions.models import (
    AnswerMessage,
    SessionStatus,
    SessionView,
    SkipMessage,
    SwapMessage,
    SwapNoteUse,
    SwapState,
)
from glean.sessions.store import (
    MAX_LEASE_SECONDS,
    STALE_QUEUED_SWAP_SECONDS,
    WORKER_TIMEOUT_SECONDS,
    MessageRefusal,
    MessageRefusedError,
    SessionBusyError,
)
from tests.agent.test_graph import KOREAN_ID, Run, call, propose_first

if TYPE_CHECKING:
    from collections.abc import Callable

NOTE = "something lighter, maybe prawns"

type Step = dict[str, Any] | BaseException | Callable[[dict[str, Any]], dict[str, Any]]


class Model:
    """The model at its boundary: a script per schema, and what it was shown on each call."""

    def __init__(self, *, plan: list[Step] | None = None, swap: list[Step] | None = None) -> None:
        self.scripts: dict[type, list[Step]] = {PlanStep: list(plan or []), SwapStep: list(swap or [])}
        self.shown: list[tuple[type, str, str]] = []

    def invoke(self, _feature: object, schema: type, *, system: str, user: str, **_kwargs: object) -> Any:
        self.shown.append((schema, system, user))
        step = self.scripts[schema].pop(0)
        if isinstance(step, BaseException):
            raise step
        if callable(step):
            step = step(json.loads(user))
        return schema.model_validate(step)

    def model_id_for(self, _feature: object, **_kwargs: object) -> str:
        return "scripted/model"

    def users(self, schema: type) -> list[dict[str, Any]]:
        return [json.loads(user) for shown, _system, user in self.shown if shown is schema]


def replace_with(pick: Callable[[dict[str, Any]], dict[str, str]], reason: str = "Lighter, as you asked.") -> Step:
    def answer(context: dict[str, Any]) -> dict[str, Any]:
        chosen = pick(context)
        return {
            "action": {
                "kind": "propose_replacement",
                "replacement": {**chosen, "reason": reason, "reason_kind": "feedback"},
            }
        }

    return answer


def a_free_candidate(context: dict[str, Any]) -> dict[str, str]:
    """The first candidate the swap says it may use."""
    unavailable = set(context["swap"]["unavailable_ids"])
    row = next(c for c in context["candidates"] if c["external_id"] not in unavailable)
    return {"external_id": row["external_id"], "title": row["title"]}


def the_locked_meal(context: dict[str, Any]) -> dict[str, str]:
    """A meal the week already has: what a model that ignores the rules would answer."""
    meal = context["swap"]["locked_week"][0]
    return {"external_id": meal["external_id"], "title": meal["title"]}


class SwapRun(Run):
    """A session that already finished its first run, so the household can swap one of its meals."""

    def __init__(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        super().__init__(tmp_path, monkeypatch)
        assert start(self.session, self.deps(Model(plan=[propose_first]))) is True
        assert self.record.status is SessionStatus.DONE
        self.proposal = self.record.result
        self.first_lines = list(self.record.progress)

    def deps(self, model: Any) -> AgentDeps:  # ty: ignore[invalid-method-override]
        return AgentDeps(
            sessions=self.sessions,
            checkpointer=self.checkpointer,
            llm_router=model,
            corpus_factory=lambda: RecipeCorpusStore(FilesystemBlobStore(self.root)),
            clock=self.clock.wall,
            monotonic=self.clock.monotonic,
            remaining_seconds=lambda: float(WORKER_TIMEOUT_SECONDS),
        )

    def swap(
        self,
        position: int = 1,
        note: str | None = NOTE,
        *,
        note_dropped: bool = False,
        week: list[str] | None = None,
    ) -> None:
        """Queue a swap as the route does: *note* is what the screen passed, *note_dropped* that it dropped one,
        *week* the cards as the app shows them (the proposal's own meals unless a test says otherwise)."""
        shown = week or self.week
        message = SwapMessage(type="swap", slot=shown[position], note=note, week=shown)
        self.sessions.enqueue_swap("user-a", "sess-1", message, note_dropped=note_dropped)

    @property
    def week(self) -> list[str]:
        return [meal.external_id or "" for meal in self.proposal.suggestions]

    def deliver(self, model: Model) -> bool:
        return start(self.session, self.deps(model))

    @property
    def view(self) -> SessionView:
        return SessionView.from_record(self.record)

    @property
    def swap_lines(self) -> list[str]:
        return self.record.progress[len(self.first_lines) :]


@pytest.fixture
def swap_run(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> SwapRun:
    return SwapRun(tmp_path, monkeypatch)


class TestReplacement:
    def test_a_swap_replaces_one_meal_explains_it_and_keeps_the_others(self, swap_run: SwapRun) -> None:
        swap_run.swap(position=1)
        model = Model(swap=[replace_with(a_free_candidate)])

        assert swap_run.deliver(model) is True

        record = swap_run.record
        assert record.status is SessionStatus.DONE
        before, after = swap_run.proposal.suggestions, record.result.suggestions
        assert after[0] == before[0]
        assert after[1].external_id != before[1].external_id
        assert after[1].reason.startswith("Lighter, as you asked.")
        assert len(after) == len(before)
        assert swap_run.swap_lines == [SWAP_NOTE_LINE, SWAP_FINALISE_LINE]
        view = swap_run.view
        assert view.swap is not None
        assert view.swap.state is SwapState.DONE
        assert view.swap.note is SwapNoteUse.USED
        assert view.swap.replacement == after[1]
        # One paid call: the model was asked once, for one replacement.
        assert len(model.shown) == 1

    def test_the_other_slots_are_locked_and_given_to_the_model_as_such(self, swap_run: SwapRun) -> None:
        swap_run.swap(position=1)
        model = Model(swap=[replace_with(a_free_candidate)])

        swap_run.deliver(model)

        swap = model.users(SwapStep)[0]["swap"]
        kept = swap_run.proposal.suggestions[0].external_id
        swapped = swap_run.proposal.suggestions[1].external_id
        assert [meal["external_id"] for meal in swap["locked_week"]] == [kept]
        assert swap["replacing"]["external_id"] == swapped
        assert {kept, swapped} <= set(swap["unavailable_ids"])

    @pytest.mark.parametrize("pick", [the_locked_meal, lambda _c: {"external_id": "rec_invented", "title": "Nope"}])
    def test_a_replacement_the_week_may_not_use_is_the_scorers_best_instead(
        self, swap_run: SwapRun, pick: Callable[[dict[str, Any]], dict[str, str]]
    ) -> None:
        swap_run.swap(position=1)

        swap_run.deliver(Model(swap=[replace_with(pick)]))

        after = swap_run.record.result.suggestions
        assert after[1].reason.startswith(TEMPLATE_SWAP_REASON)
        assert after[1].external_id not in {s.external_id for s in swap_run.proposal.suggestions}
        assert after[0] == swap_run.proposal.suggestions[0]
        assert swap_run.view.swap.state is SwapState.DONE  # ty: ignore[possibly-missing-attribute]
        assert swap_run.metric("SwapsDegraded") == [1]

    def test_a_meal_already_in_the_plan_is_never_the_replacement(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from tests.agent import test_graph  # noqa: PLC0415

        planned = "rec_05"
        original = test_graph._request

        def with_planned() -> Any:
            return original().model_copy(update={"exclude_external_ids": [planned]})

        monkeypatch.setattr(test_graph, "_request", with_planned)
        run = SwapRun(tmp_path, monkeypatch)
        run.swap(position=1)
        model = Model(swap=[replace_with(lambda _c: {"external_id": planned, "title": "Synthetic dish 05"})])

        run.deliver(model)

        assert planned in model.users(SwapStep)[0]["swap"]["unavailable_ids"]
        assert planned not in [s.external_id for s in run.record.result.suggestions]

    def test_the_swap_locks_and_scores_the_week_on_screen_not_the_servers(self, swap_run: SwapRun) -> None:
        """After a local Undo the app shows the original meal again; the next swap must keep that one."""
        swap_run.swap(position=1)
        swap_run.deliver(Model(swap=[replace_with(a_free_candidate)]))
        original = swap_run.proposal.suggestions[1].external_id
        assert swap_run.record.result.suggestions[1].external_id != original
        on_screen = swap_run.week  # the app undid the swap: the original meal is back on its card
        swap_run.swap(position=0, week=on_screen)
        model = Model(swap=[replace_with(a_free_candidate)])

        swap_run.deliver(model)

        swap = model.users(SwapStep)[0]["swap"]
        assert [meal["external_id"] for meal in swap["locked_week"]] == [original]
        assert original in swap["unavailable_ids"]
        assert swap_run.record.result.suggestions[0].external_id not in on_screen

    def test_the_agent_can_search_for_what_the_note_asks_for(self, swap_run: SwapRun) -> None:
        swap_run.swap(position=0, note="something korean")

        def found(context: dict[str, Any]) -> dict[str, str]:
            row = next(
                row
                for result in context["tool_results"]
                for row in (result.get("data") or {}).get("recipes", [])
                if row["external_id"] == KOREAN_ID
            )
            return {"external_id": row["external_id"], "title": row["title"]}

        model = Model(swap=[call("get_eligible_recipes", filter={"text": "korean"}), replace_with(found)])

        swap_run.deliver(model)

        assert swap_run.record.result.suggestions[0].external_id == KOREAN_ID
        assert swap_run.swap_lines == [SWAP_NOTE_LINE, "Looking for something Korean", SWAP_FINALISE_LINE]

    def test_a_swap_spends_at_most_its_own_tool_budget(self, swap_run: SwapRun) -> None:
        swap_run.swap()
        model = Model(swap=[call("get_recipes", ids=["rec_01"])] * (MAX_SWAP_TOOL_CALLS + 1))

        swap_run.deliver(model)

        assert swap_run.swap_lines.count("Reading the recipes more closely") == MAX_SWAP_TOOL_CALLS
        assert swap_run.record.result.suggestions[1].reason.startswith(TEMPLATE_SWAP_REASON)

    def test_a_provider_error_is_the_scorers_replacement(self, swap_run: SwapRun) -> None:
        swap_run.swap()

        swap_run.deliver(Model(swap=[RuntimeError("provider fell over")]))

        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.record.result.suggestions[1].reason.startswith(TEMPLATE_SWAP_REASON)

    def test_with_nothing_left_to_swap_in_the_proposal_stays_as_it_was(
        self, swap_run: SwapRun, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        swap_run.swap()
        monkeypatch.setattr("glean.meal_plan.pipeline.best_replacement", lambda *_a, **_k: None)

        swap_run.deliver(Model(swap=[replace_with(the_locked_meal)]))

        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.record.result == swap_run.proposal
        assert swap_run.view.swap.state is SwapState.NO_REPLACEMENT  # ty: ignore[possibly-missing-attribute]

    def test_a_bug_in_the_swap_fails_the_swap_not_the_week(
        self, swap_run: SwapRun, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        swap_run.swap()

        def broken(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("a bug")

        monkeypatch.setattr("glean.meal_plan.pipeline.replacement", broken)

        assert swap_run.deliver(Model(swap=[replace_with(a_free_candidate)])) is True

        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.record.result == swap_run.proposal
        assert swap_run.view.swap.state is SwapState.FAILED  # ty: ignore[possibly-missing-attribute]


class TestNote:
    def test_the_screened_note_reaches_the_model_only_as_data(self, swap_run: SwapRun) -> None:
        swap_run.swap(note=NOTE)
        model = Model(swap=[replace_with(a_free_candidate)])

        swap_run.deliver(model)

        _schema, system, user = model.shown[0]
        assert NOTE not in system
        assert json.loads(user)["swap"]["swap_note"] == NOTE
        assert user.count(NOTE) == 1
        assert swap_run.view.swap.note is SwapNoteUse.USED  # ty: ignore[possibly-missing-attribute]

    def test_a_dropped_note_leaves_nothing_for_the_model_and_the_swap_still_runs(self, swap_run: SwapRun) -> None:
        swap_run.swap(note=None, note_dropped=True)
        model = Model(swap=[replace_with(a_free_candidate)])

        swap_run.deliver(model)

        assert json.loads(model.shown[0][2])["swap"]["swap_note"] is None
        assert swap_run.swap_lines == [SWAP_LINE, SWAP_FINALISE_LINE]
        view = swap_run.view
        assert view.swap is not None
        assert view.swap.state is SwapState.DONE
        assert view.swap.note is SwapNoteUse.DROPPED

    def test_a_swap_without_a_note_says_so(self, swap_run: SwapRun) -> None:
        swap_run.swap(note=None)

        swap_run.deliver(Model(swap=[replace_with(a_free_candidate)]))

        assert swap_run.swap_lines == [SWAP_LINE, SWAP_FINALISE_LINE]
        assert swap_run.view.swap.note is SwapNoteUse.NONE  # ty: ignore[possibly-missing-attribute]


class TestLease:
    def test_a_duplicate_delivery_after_the_swap_finished_does_nothing(self, swap_run: SwapRun) -> None:
        swap_run.swap()
        swap_run.deliver(Model(swap=[replace_with(a_free_candidate)]))
        finished = swap_run.record

        late = Model()
        assert swap_run.deliver(late) is False

        assert late.shown == []
        assert swap_run.record.result == finished.result
        assert swap_run.record.progress == finished.progress

    def test_a_duplicate_delivery_while_the_swap_runs_is_sent_back(self, swap_run: SwapRun) -> None:
        swap_run.swap()
        swap_run.sessions.claim(
            "user-a", "sess-1", owner="live", now=swap_run.clock.now, lease_seconds=MAX_LEASE_SECONDS
        )

        with pytest.raises(SessionBusyError):
            swap_run.deliver(Model())

    def test_a_stale_start_message_runs_the_queued_swap_once(self, swap_run: SwapRun) -> None:
        """The first run's message, redelivered after a swap was queued, finds the swap and does that."""
        swap_run.swap()
        model = Model(swap=[replace_with(a_free_candidate)])

        assert swap_run.deliver(model) is True
        assert swap_run.deliver(Model()) is False

        assert len(model.shown) == 1
        assert swap_run.view.swap.state is SwapState.DONE  # ty: ignore[possibly-missing-attribute]

    def test_a_stale_first_run_delivery_never_publishes_the_old_week_over_swaps(self, swap_run: SwapRun) -> None:
        """What runs is decided from the item the claim won, so an old message can only do the item's work."""
        swap_run.swap(position=1)
        swap_run.deliver(Model(swap=[replace_with(a_free_candidate)]))
        first = swap_run.record.result.suggestions[1]
        assert first != swap_run.proposal.suggestions[1]
        swap_run.proposal = swap_run.record.result
        swap_run.swap(position=0)

        stale = Model(swap=[replace_with(a_free_candidate)])
        assert swap_run.deliver(stale) is True

        record = swap_run.record
        assert record.status is SessionStatus.DONE
        assert record.result.suggestions[1] == first
        assert record.result.suggestions[0] != swap_run.proposal.suggestions[0]
        assert [swap.state for swap in record.swaps] == [SwapState.DONE, SwapState.DONE]
        assert [schema for schema, _system, _user in stale.shown] == [SwapStep]

    def test_a_crash_mid_swap_resumes_from_the_checkpoint_without_repeating_the_tool(self, swap_run: SwapRun) -> None:
        class ProcessDied(BaseException):
            """A killed Lambda, from inside Python: nothing catches it."""

        swap_run.swap(position=0, note="something korean")
        dead = Model(swap=[call("get_eligible_recipes", filter={"text": "korean"}), ProcessDied()])
        with pytest.raises(ProcessDied):
            swap_run.deliver(dead)
        assert swap_run.record.status is SessionStatus.RUNNING

        swap_run.clock.advance(MAX_LEASE_SECONDS + 10)
        resumed = Model(swap=[replace_with(a_free_candidate)])
        assert swap_run.deliver(resumed) is True

        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.swap_lines.count("Looking for something Korean") == 1
        assert swap_run.swap_lines.count(SWAP_NOTE_LINE) == 1
        assert len(resumed.shown) == 1
        assert len(resumed.users(SwapStep)[0]["tool_results"]) == 1
        assert swap_run.view.swap.state is SwapState.DONE  # ty: ignore[possibly-missing-attribute]

    def test_a_crash_after_the_swap_was_made_publishes_it_without_asking_again(
        self, swap_run: SwapRun, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class ProcessDied(BaseException):
            """The worker died between the last node and the session write."""

        swap_run.swap()
        real = swap_run.sessions.finish_swap

        def dies(*_args: Any, **_kwargs: Any) -> bool:
            raise ProcessDied

        monkeypatch.setattr(swap_run.sessions, "finish_swap", dies)
        first = Model(swap=[replace_with(a_free_candidate)])
        with pytest.raises(ProcessDied):
            swap_run.deliver(first)
        monkeypatch.setattr(swap_run.sessions, "finish_swap", real)

        swap_run.clock.advance(MAX_LEASE_SECONDS + 10)
        again = Model()
        assert swap_run.deliver(again) is True

        assert again.shown == []
        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.record.result.suggestions[1].reason.startswith("Lighter, as you asked.")

    def test_a_swap_after_the_checkpoint_expired_still_runs(self, swap_run: SwapRun) -> None:
        swap_run.checkpointer = in_memory_checkpointer()
        swap_run.swap()

        swap_run.deliver(Model(swap=[replace_with(a_free_candidate)]))

        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.view.swap.state is SwapState.DONE  # ty: ignore[possibly-missing-attribute]
        assert swap_run.record.result.suggestions[0] == swap_run.proposal.suggestions[0]

    def test_a_cancel_mid_swap_stops_it(self, swap_run: SwapRun) -> None:
        swap_run.swap()

        def cancels(_context: dict[str, Any]) -> dict[str, Any]:
            swap_run.sessions.cancel("user-a", "sess-1")
            return call("get_recipes", ids=["rec_01"])

        swap_run.deliver(Model(swap=[cancels]))

        assert swap_run.record.status is SessionStatus.CANCELLED
        assert "Reading the recipes more closely" not in swap_run.swap_lines

    def test_a_second_swap_cannot_bring_back_the_meal_the_first_swapped_out(self, swap_run: SwapRun) -> None:
        swap_run.swap(position=1)
        swap_run.deliver(Model(swap=[replace_with(a_free_candidate)]))
        out = swap_run.proposal.suggestions[1].external_id
        swap_run.proposal = swap_run.record.result
        swap_run.swap(position=0)
        model = Model(swap=[replace_with(lambda _c: {"external_id": out, "title": "Back again"})])

        swap_run.deliver(model)

        assert out in model.users(SwapStep)[0]["swap"]["unavailable_ids"]
        assert out not in [s.external_id for s in swap_run.record.result.suggestions]


class TestWorker:
    def test_the_worker_resumes_a_session_whose_swap_is_queued(self, swap_run: SwapRun) -> None:
        from glean.sessions.queue import SessionMessage  # noqa: PLC0415
        from glean.worker import handle_record  # noqa: PLC0415

        swap_run.swap()
        body = SessionMessage(session_id="sess-1", user_sub="user-a").model_dump_json()
        model = Model(swap=[replace_with(a_free_candidate)])

        assert handle_record({"body": body, "receiptHandle": "r-1"}, swap_run.deps(model)) is True

        assert swap_run.view.swap.state is SwapState.DONE  # ty: ignore[possibly-missing-attribute]
        assert len(model.users(SwapStep)) == 1


class TestResume:
    """`agent.resume(session_id, message)`: the deep module's call for a household message (spec §6.2)."""

    def test_a_swap_is_stored_and_its_session_sent_back_to_the_queue(self, swap_run: SwapRun) -> None:
        sent: list[Any] = []
        slot = swap_run.proposal.suggestions[1].external_id

        swap_id = resume(
            "sess-1",
            SwapMessage(type="swap", slot=slot, note=NOTE, week=swap_run.week),
            user_sub="user-a",
            sessions=swap_run.sessions,
            dispatch=sent.append,
        )

        assert swap_id == 1
        assert [session.session_id for session in sent] == ["sess-1"]
        assert swap_run.record.status is SessionStatus.QUEUED
        assert swap_run.record.pending_swap is not None

    @pytest.mark.parametrize("message", [AnswerMessage(type="answer", option="Fish"), SkipMessage(type="skip")])
    def test_an_answer_or_skip_with_no_run_parked_is_refused(
        self, swap_run: SwapRun, message: AnswerMessage | SkipMessage
    ) -> None:
        with pytest.raises(MessageRefusedError) as refused:
            resume("sess-1", message, user_sub="user-a", sessions=swap_run.sessions, dispatch=lambda _s: None)

        assert refused.value.reason is MessageRefusal.NO_QUESTION
        assert swap_run.record.status is SessionStatus.DONE

    def test_a_queue_that_will_not_take_it_fails_the_session_and_keeps_the_proposal(self, swap_run: SwapRun) -> None:
        def down(_session: Any) -> None:
            raise RuntimeError("queue down")

        slot = swap_run.proposal.suggestions[0].external_id
        with pytest.raises(MessageNotSent):
            resume(
                "sess-1",
                SwapMessage(type="swap", slot=slot, week=swap_run.week),
                user_sub="user-a",
                sessions=swap_run.sessions,
                dispatch=down,
            )

        assert swap_run.record.status is SessionStatus.FAILED
        assert swap_run.record.result == swap_run.proposal
        assert swap_run.view.swap.state is SwapState.FAILED  # ty: ignore[possibly-missing-attribute]

    def test_a_crash_between_storing_a_swap_and_sending_it_does_not_block_the_next(self, swap_run: SwapRun) -> None:
        class ProcessDied(BaseException):
            """The API Lambda died after the store write and before the queue send."""

        def dies(_session: Any) -> None:
            raise ProcessDied

        slots = [meal.external_id for meal in swap_run.proposal.suggestions]
        with pytest.raises(ProcessDied):
            resume(
                "sess-1",
                SwapMessage(type="swap", slot=slots[1], week=slots),
                user_sub="user-a",
                sessions=swap_run.sessions,
                dispatch=dies,
            )
        assert swap_run.record.status is SessionStatus.QUEUED
        with pytest.raises(MessageRefusedError):
            resume(
                "sess-1",
                SwapMessage(type="swap", slot=slots[0], week=slots),
                user_sub="user-a",
                sessions=swap_run.sessions,
                dispatch=lambda _s: None,
            )

        swap_run.clock.advance(STALE_QUEUED_SWAP_SECONDS)
        sent: list[Any] = []
        swap_id = resume(
            "sess-1",
            SwapMessage(type="swap", slot=slots[0], week=slots),
            user_sub="user-a",
            sessions=swap_run.sessions,
            dispatch=sent.append,
        )
        model = Model(swap=[replace_with(a_free_candidate)])
        assert swap_run.deliver(model) is True

        assert swap_id == 2
        assert [swap.state for swap in swap_run.record.swaps] == [SwapState.FAILED, SwapState.DONE]
        assert swap_run.record.status is SessionStatus.DONE
        assert swap_run.record.result.suggestions[0] != swap_run.proposal.suggestions[0]
        assert swap_run.record.result.suggestions[1] == swap_run.proposal.suggestions[1]
