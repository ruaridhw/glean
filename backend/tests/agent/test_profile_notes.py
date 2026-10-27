"""V15: the agent's profile notes, from its `propose` action to the proposal (spec §6.4 "Feedback into the profile").

Seam: `agent.start`, with the model scripted at `LLMRouter.invoke` as in `test_graph`. These pin which evidence the
graph hands `kept_notes` (a rated cook, an answered question, a swap note), that a degraded week carries none,
that a swap carries the proposal's notes unchanged, and what the prompt shows the model. They miss whether a real
model writes good notes, which only an eval can measure.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import pytest

from glean.agent import graph, start
from glean.agent.prompts import AGENT_SYSTEM_PROMPT, SWAP_SYSTEM_PROMPT
from glean.sessions.models import HouseholdReply, SessionStatus, SwapMessage
from tests.agent.test_graph import NOTE, Run, ScriptedModel, _request, ask, propose_first
from tests.agent.test_swap import Model, a_free_candidate, replace_with

if TYPE_CHECKING:
    from glean.meal_plan.schemas import MealPlanRequest, ProfileNote

RICE = {"text": "You prefer rice over pasta midweek.", "evidence": "rating"}
KIDS = {"text": "The kids don't like spicy food.", "evidence": "answer"}
SWAPPED = {"text": "You like prawns.", "evidence": "swap_note"}


def noting(*notes: dict[str, str]) -> Any:
    """Propose the scorer's first week with *notes*, as a model that noticed something would."""

    def answer(context: dict[str, Any]) -> dict[str, Any]:
        step = propose_first(context)
        step["action"]["profile_notes"] = list(notes)
        return step

    return answer


def texts(notes: list[ProfileNote]) -> list[str]:
    return [note.text for note in notes]


def unrated() -> MealPlanRequest:
    request = _request()
    return request.model_copy(
        update={"cooked_history": [item.model_copy(update={"rating": None}) for item in request.cooked_history]}
    )


@pytest.fixture
def run(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Run:
    return Run(tmp_path, monkeypatch)


def _finished(caplog: pytest.LogCaptureFixture) -> Any:
    return next(record for record in caplog.records if record.getMessage() == "agent session finished")


class TestEvidence:
    def test_a_note_resting_on_a_rated_cook_reaches_the_proposal(self, run: Run) -> None:
        run.start(ScriptedModel(noting(RICE)))

        assert run.record.status is SessionStatus.DONE
        assert texts(run.record.result.profile_notes) == [RICE["text"]]

    def test_a_rating_note_without_a_rated_cook_is_dropped_and_counted(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        run = Run(tmp_path, monkeypatch, request=unrated())
        caplog.set_level(logging.INFO)

        run.start(ScriptedModel(noting(RICE)))

        assert run.record.result.profile_notes == []
        finished = _finished(caplog)
        assert finished.profile_notes_kept == 0
        assert finished.profile_notes_dropped == {"no_evidence": 1}

    def test_a_rated_cook_of_the_households_own_recipe_is_not_evidence(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        request = _request()
        own = request.model_copy(
            update={"cooked_history": [item.model_copy(update={"recipe_id": None}) for item in request.cooked_history]}
        )
        run = Run(tmp_path, monkeypatch, request=own)
        model = ScriptedModel(noting(RICE))

        run.start(model)

        assert json.loads(model.users[0])["rated_meals"] == []
        assert run.record.result.profile_notes == []

    def test_an_answer_note_needs_the_question_answered(self, run: Run) -> None:
        run.start(ScriptedModel(ask()))
        run.sessions.answer("user-a", "sess-1", HouseholdReply(option="No"))

        run.start(ScriptedModel(noting(KIDS)))

        assert texts(run.record.result.profile_notes) == [KIDS["text"]]

    def test_a_skipped_question_is_no_evidence(self, run: Run) -> None:
        run.start(ScriptedModel(ask()))
        run.sessions.answer("user-a", "sess-1", HouseholdReply(skipped=True))

        run.start(ScriptedModel(noting(KIDS, RICE)))

        assert texts(run.record.result.profile_notes) == [RICE["text"]]

    def test_an_answer_note_with_no_question_is_dropped(self, run: Run) -> None:
        run.start(ScriptedModel(noting(KIDS)))

        assert run.record.result.profile_notes == []

    def test_the_weeks_run_has_no_swap_note_to_rest_on(self, run: Run) -> None:
        run.start(ScriptedModel(noting(SWAPPED, RICE)))

        assert texts(run.record.result.profile_notes) == [RICE["text"]]

    def test_the_limits_apply_on_the_way_into_the_proposal(self, run: Run) -> None:
        notes = [RICE, {**RICE, "text": RICE["text"].upper()}, *({**RICE, "text": f"Note {i}"} for i in range(4))]

        run.start(ScriptedModel(noting(*notes)))

        assert texts(run.record.result.profile_notes) == [RICE["text"], "Note 0", "Note 1"]


class TestKnown:
    def test_a_note_the_profile_already_knows_is_dropped(self, run: Run, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(graph, "known_notes", lambda _request: [RICE["text"].lower()])

        run.start(ScriptedModel(noting(RICE, KIDS | {"evidence": "rating"})))

        assert texts(run.record.result.profile_notes) == [KIDS["text"]]


class TestNoNotes:
    def test_a_proposal_without_notes_has_none(self, run: Run) -> None:
        run.start(ScriptedModel(propose_first))

        assert run.record.result.profile_notes == []

    def test_a_degraded_week_carries_no_notes(self, run: Run) -> None:
        def invented(context: dict[str, Any]) -> dict[str, Any]:
            step = noting(RICE)(context)
            for meal in step["action"]["proposal"]["suggestions"]:
                meal["external_id"] = f"{meal['external_id']}_invented"
            return step

        run.start(ScriptedModel(invented))

        assert run.record.result.degraded is True
        assert run.record.result.profile_notes == []


class TestSwap:
    def test_notes_survive_a_swap(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        run = Run(tmp_path, monkeypatch)
        assert start(run.session, run.deps(Model(plan=[noting(RICE)]))) is True  # ty: ignore[invalid-argument-type]
        before = run.record.result
        assert texts(before.profile_notes) == [RICE["text"]]
        week = [meal.external_id or "" for meal in before.suggestions]
        run.sessions.enqueue_swap(
            "user-a", "sess-1", SwapMessage(type="swap", slot=week[1], note="prawns", week=week), note_rejection=None
        )

        start(run.session, run.deps(Model(swap=[replace_with(a_free_candidate)])))  # ty: ignore[invalid-argument-type]

        after = run.record.result
        assert after.suggestions[1].external_id != before.suggestions[1].external_id
        assert after.profile_notes == before.profile_notes


PRAWNS = {"text": "You like prawns.", "evidence": "swap_note"}


def _swapped(
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    week_notes: tuple[dict[str, str], ...] = (RICE,),
    swap_notes: tuple[dict[str, str], ...] = (PRAWNS,),
    note: str | None = "prawns, please",
    pick: Any = a_free_candidate,
) -> tuple[Any, Any, Model]:
    """Run a week that notes *week_notes*, then a swap whose replacement notes *swap_notes*."""
    run = Run(tmp_path, monkeypatch)
    assert start(run.session, run.deps(Model(plan=[noting(*week_notes)]))) is True  # ty: ignore[invalid-argument-type]
    before = run.record.result
    week = [meal.external_id or "" for meal in before.suggestions]
    run.sessions.enqueue_swap(
        "user-a", "sess-1", SwapMessage(type="swap", slot=week[1], note=note, week=week), note_rejection=None
    )
    replace = replace_with(pick)

    def answer(context: dict[str, Any]) -> dict[str, Any]:
        step = replace(context)  # ty: ignore[call-non-callable]
        step["action"]["profile_notes"] = list(swap_notes)
        return step

    model = Model(swap=[answer])
    start(run.session, run.deps(model))  # ty: ignore[invalid-argument-type]
    return before, run.record.result, model


class TestSwapNotes:
    def test_a_swap_adds_a_note_resting_on_its_own_note(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        before, after, _ = _swapped(tmp_path, monkeypatch)

        assert after.suggestions[1].external_id != before.suggestions[1].external_id
        assert texts(after.profile_notes) == [RICE["text"], PRAWNS["text"]]

    def test_a_swap_without_a_note_adds_none(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        _, after, _ = _swapped(tmp_path, monkeypatch, note=None)

        assert texts(after.profile_notes) == [RICE["text"]]

    def test_only_the_swap_note_is_evidence_in_a_swap(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        # The week's run had a rated cook, but a swap's own notes may rest only on the swap's note.
        _, after, _ = _swapped(tmp_path, monkeypatch, swap_notes=({**PRAWNS, "evidence": "rating"},))

        assert texts(after.profile_notes) == [RICE["text"]]

    def test_merged_notes_are_deduplicated_and_still_at_most_three(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        week = (RICE, {**RICE, "text": "Cooks for four."})
        swap = ({**PRAWNS, "text": RICE["text"].upper()}, PRAWNS, {**PRAWNS, "text": "Likes it lighter."})

        _, after, _ = _swapped(tmp_path, monkeypatch, week_notes=week, swap_notes=swap)

        assert texts(after.profile_notes) == [RICE["text"], "Cooks for four.", PRAWNS["text"]]

    def test_a_swap_that_falls_back_adds_no_notes(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        def invented(_context: dict[str, Any]) -> dict[str, str]:
            return {"external_id": "rec_invented", "title": "Nope"}

        _, after, _ = _swapped(tmp_path, monkeypatch, pick=invented)

        assert texts(after.profile_notes) == [RICE["text"]]

    def test_the_swap_rules_ask_for_notes_only_from_the_swap_note(self) -> None:
        assert "profile_notes" in SWAP_SYSTEM_PROMPT
        assert "swap_note" in SWAP_SYSTEM_PROMPT.split("profile_notes", 1)[1]


class TestPrompt:
    def test_the_rules_ask_for_notes_only_on_durable_evidence_and_frame_them_as_data(self) -> None:
        assert "profile_notes" in AGENT_SYSTEM_PROMPT
        assert "durable" in AGENT_SYSTEM_PROMPT
        assert "rated_meals" in AGENT_SYSTEM_PROMPT

    def test_the_model_sees_rated_cooks_as_title_and_thumb_never_their_note(self, run: Run) -> None:
        model = ScriptedModel(propose_first)

        run.start(model)

        context = json.loads(model.users[0])
        assert context["rated_meals"] == [{"title": "Synthetic dish 00", "rating": "up"}]
        assert NOTE not in model.users[0]
