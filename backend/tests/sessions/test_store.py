"""The session store contract, run against the in-memory store and against DynamoDB (moto).

The DynamoDB table is built from `template.yaml`'s own properties, so a property the stack needs and
the tests do not set -- or the other way round -- fails here rather than at deploy time.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from glean.meal_plan.schemas import (
    MealPlanAlternative,
    MealPlanRequest,
    MealPlanResult,
    MealPlanSuggestion,
    PlannedMealAlternative,
)
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.models import (
    MAX_ITEM_BYTES,
    MAX_PROGRESS_LINES,
    MAX_STORED_INPUT_BYTES,
    MAX_SWAPS_KEPT,
    SESSION_TTL_HOURS,
    AbandonResult,
    AgentSession,
    ClaimResult,
    SessionError,
    SessionErrorCode,
    SessionStatus,
    SessionView,
    SwapMessage,
    SwapNoteUse,
    SwapRecord,
    SwapState,
    stored_input_bytes,
)
from glean.sessions.store import (
    LAMBDA_INIT_SECONDS,
    MAX_LEASE_SECONDS,
    QUEUE_VISIBILITY_MARGIN_SECONDS,
    QUEUE_VISIBILITY_SECONDS,
    STALE_QUEUED_SWAP_SECONDS,
    WORKER_TIMEOUT_SECONDS,
    InMemorySessionStore,
    MessageRefusal,
    MessageRefusedError,
    SessionTooLargeError,
    UnknownSessionError,
    lease_seconds_for,
)
from tests.infra.cfn import sessions_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

    from glean.sessions.store import SessionStore

TABLE_NAME = "glean-agent-sessions-test"
REGION = "eu-west-2"
# The lease a claim at the first instant of a full invocation takes: its remaining time plus the grace.
FULL_INVOCATION_LEASE = lease_seconds_for(WORKER_TIMEOUT_SECONDS)
# CloudFormation-only properties that create_table does not take; the TTL is applied separately.
_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification", "TimeToLiveSpecification"}
START = datetime(2026, 10, 22, 12, tzinfo=UTC)


class Clock:
    def __init__(self, now: datetime = START) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture(params=["memory", "dynamo"])
def store(request: pytest.FixtureRequest) -> Iterator[tuple[SessionStore, Clock]]:
    clock = Clock()
    if request.param == "memory":
        yield InMemorySessionStore(clock=clock), clock
        return
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        properties = {key: value for key, value in sessions_table_properties().items() if key not in _CFN_ONLY}
        dynamodb.create_table(TableName=TABLE_NAME, **properties)
        yield DynamoSessionStore(TABLE_NAME, region=REGION, clock=clock), clock


def _request(**overrides: Any) -> MealPlanRequest:
    return MealPlanRequest(
        **{
            "source": "corpus",
            "pantry": [],
            "meals_per_week": 3,
            "purchase_tolerance": 0.3,
            "dietary_flags": [],
            "max_active_time_mins": None,
            **overrides,
        }
    )


def _session(session_id: str = "sess-1", user_sub: str = "user-a", **overrides: Any) -> AgentSession:
    return AgentSession(session_id=session_id, user_sub=user_sub, request=_request(**overrides))


def _result() -> MealPlanResult:
    return MealPlanResult(suggestions=[MealPlanSuggestion(external_id="rec_1", title="Lentil Bake", reason="Cheap.")])


def test_a_new_session_is_queued_and_holds_its_inputs(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store

    sessions.create(_session(), now=clock.now)
    record = sessions.get("user-a", "sess-1")

    assert record is not None
    assert record.status is SessionStatus.QUEUED
    assert record.request == _request()
    assert record.progress == []
    assert record.result is None
    assert record.error is None
    assert record.owner is None
    assert record.lease_until is None
    assert record.created_at == START
    assert record.updated_at == START


def test_the_inputs_are_stored_compressed(store: tuple[SessionStore, Clock], tmp_path: Any) -> None:
    sessions, clock = store
    request = _request(
        cooked_history=[{"recipe_id": None, "title": "Lentil Bake", "cooked_at": START.isoformat()}],
    )

    sessions.create(_session(), now=clock.now)

    # A second session carrying a history row round-trips, and the stored bytes are compressed: the
    # gzip of the JSON is far smaller than the JSON itself.
    sessions.create(
        AgentSession(session_id="sess-2", user_sub="user-a", request=request),
        now=clock.now,
    )
    record = sessions.get("user-a", "sess-2")

    assert record is not None
    assert record.request == request
    assert stored_input_bytes(request) < len(request.model_dump_json())


def test_a_session_expires_a_day_after_its_last_update(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store

    sessions.create(_session(), now=clock.now)
    first = sessions.get("user-a", "sess-1")
    clock.advance(hours=6)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    second = sessions.get("user-a", "sess-1")

    assert first is not None
    assert second is not None
    assert first.ttl == int((START + timedelta(hours=SESSION_TTL_HOURS)).timestamp())
    assert second.ttl == int((clock.now + timedelta(hours=SESSION_TTL_HOURS)).timestamp())
    assert second.updated_at == clock.now


def test_polling_a_session_never_writes(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    before = sessions.get("user-a", "sess-1")

    for _ in range(3):
        assert sessions.get("user-a", "sess-1") == before


def test_the_in_memory_store_counts_its_writes() -> None:
    sessions = InMemorySessionStore(clock=Clock())
    sessions.create(_session(), now=START)
    after_create = sessions.writes

    for _ in range(5):
        sessions.get("user-a", "sess-1")

    assert sessions.writes == after_create


def test_another_users_session_is_unreachable_by_key(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)

    assert sessions.get("user-b", "sess-1") is None
    with pytest.raises(UnknownSessionError):
        sessions.claim("user-b", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    assert sessions.get("user-a", "sess-1").status is SessionStatus.QUEUED


def test_claiming_a_queued_session_wins_once_and_a_live_duplicate_is_told_so(
    store: tuple[SessionStore, Clock],
) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)

    first = sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    duplicate = sessions.claim(
        "user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE
    )

    assert (first, duplicate) == (ClaimResult.STARTED, ClaimResult.OWNED_ELSEWHERE)
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert (record.status, record.owner) == (SessionStatus.RUNNING, "attempt-1")
    assert record.lease_until == int(clock.now.timestamp()) + FULL_INVOCATION_LEASE


def test_a_claim_after_the_lease_lapsed_takes_the_session_over(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)

    takeover = sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    assert takeover is ClaimResult.RESUMED
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.owner == "attempt-2"


def test_a_finished_session_cannot_be_claimed_again(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")

    assert (
        sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
        is ClaimResult.FINISHED
    )
    record = sessions.get("user-a", "sess-1")
    assert record.status is SessionStatus.DONE
    assert record.result == _result()


def test_the_lease_is_taken_once_and_never_extended(store: tuple[SessionStore, Clock]) -> None:
    """The lease is anchored to the attempt's deadline and never extended."""
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    claimed_at = int(clock.now.timestamp())

    clock.advance(seconds=FULL_INVOCATION_LEASE // 2)
    sessions.append_progress("user-a", "sess-1", ["working"], owner="attempt-1")
    sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert record.lease_until == claimed_at + FULL_INVOCATION_LEASE


def test_the_lease_ends_just_after_the_invocation_it_belongs_to() -> None:
    """The lease is the caller's remaining time plus a grace, so it ends when its own worker certainly has."""
    assert lease_seconds_for(120) == 122
    assert lease_seconds_for(0.4) == 3  # ceiled, never rounded down
    assert lease_seconds_for(WORKER_TIMEOUT_SECONDS) == MAX_LEASE_SECONDS


def test_the_visibility_timeout_covers_every_invocation_that_can_claim() -> None:
    """A message must stay invisible past any run's lease, including one that claimed late after init."""
    assert LAMBDA_INIT_SECONDS + MAX_LEASE_SECONDS < QUEUE_VISIBILITY_SECONDS
    assert QUEUE_VISIBILITY_SECONDS > WORKER_TIMEOUT_SECONDS + LAMBDA_INIT_SECONDS + QUEUE_VISIBILITY_MARGIN_SECONDS


def test_an_attempt_that_lost_the_lease_cannot_write_the_outcome(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    stale_progress = sessions.append_progress("user-a", "sess-1", ["late"], owner="attempt-1")
    stale_complete = sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")
    stale_fail = sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED), owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert (stale_progress, stale_complete, stale_fail) == (False, False, False)
    assert record.status is SessionStatus.RUNNING
    assert record.result is None
    assert record.progress == []


def test_progress_lines_are_returned_from_a_cursor(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.append_progress("user-a", "sess-1", ["Preparing", "Planning", "Finishing"], owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert record.next_cursor == 3
    assert record.with_lines_since(0) == (["Preparing", "Planning", "Finishing"], 3)
    assert record.with_lines_since(2) == (["Finishing"], 3)
    assert record.with_lines_since(3) == ([], 3)


def test_the_progress_list_is_bounded_and_older_lines_drop_out(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.append_progress(
        "user-a", "sess-1", [f"line {index}" for index in range(MAX_PROGRESS_LINES + 5)], owner="attempt-1"
    )

    record = sessions.get("user-a", "sess-1")
    assert len(record.progress) == MAX_PROGRESS_LINES
    assert record.progress_start == 5
    assert record.progress[0] == "line 5"
    assert record.next_cursor == MAX_PROGRESS_LINES + 5
    # A cursor from before the bound still gets every line the item still holds.
    assert record.with_lines_since(0) == (record.progress, MAX_PROGRESS_LINES + 5)


def test_failing_a_session_records_the_typed_code(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    moved = sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.MODEL_ERROR), owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert moved is True
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)
    assert record.result is None


def test_a_rate_limited_failure_carries_its_wait(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    sessions.fail(
        "user-a",
        "sess-1",
        SessionError(code=SessionErrorCode.RATE_LIMITED, retry_after_minutes=12),
        owner="attempt-1",
    )

    assert sessions.get("user-a", "sess-1").error == SessionError(
        code=SessionErrorCode.RATE_LIMITED, retry_after_minutes=12
    )


def test_the_dead_letter_handler_fails_a_session_whose_attempt_has_gone(
    store: tuple[SessionStore, Clock],
) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)

    outcome = sessions.fail_if_abandoned("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    assert outcome is AbandonResult.FAILED
    assert sessions.get("user-a", "sess-1").status is SessionStatus.FAILED


def test_an_ownerless_failure_leaves_a_live_run_alone(store: tuple[SessionStore, Clock]) -> None:
    """The dead-letter handler may only fail a session whose attempt is gone; a live one finishes itself."""
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    while_live = sessions.fail_if_abandoned("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)
    after_the_lease = sessions.fail_if_abandoned("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    assert while_live is AbandonResult.STILL_LIVE
    assert after_the_lease is AbandonResult.FAILED
    assert sessions.get("user-a", "sess-1").status is SessionStatus.FAILED


def test_a_finished_session_is_never_failed_afterwards(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")

    outcome = sessions.fail_if_abandoned("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    record = sessions.get("user-a", "sess-1")
    assert outcome is AbandonResult.FINISHED
    assert record.status is SessionStatus.DONE
    assert record.error is None


def test_the_largest_history_the_app_sends_compresses_into_one_item(store: tuple[SessionStore, Clock]) -> None:
    """The review's case: 2,500 saved recipes (464 KB of JSON) used to fail PutItem.

    Stored gzipped it is a fraction of that, so the request the app really sends fits.
    """
    sessions, clock = store
    crowded = _request(
        recipe_history=[
            {
                "recipe_id": index,
                "title": (
                    "Slow-cooked beef ragu with tagliatelle, a Sunday sauce for the whole family "
                    f"and enough for Monday lunches {index}"
                ),
                "last_cooked_at": None,
                "food_groups": ["protein", "veg"],
            }
            for index in range(2500)
        ]
    )
    assert len(crowded.model_dump_json()) > MAX_ITEM_BYTES  # the JSON alone is over one item
    assert stored_input_bytes(crowded) < MAX_STORED_INPUT_BYTES

    sessions.create(AgentSession(session_id="sess-large", user_sub="user-a", request=crowded), now=clock.now)

    record = sessions.get("user-a", "sess-large")
    assert record is not None
    assert record.request == crowded


def test_create_refuses_inputs_that_would_not_fit_one_item(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    # Nothing bounds a recipe title's length, so an absurd one can still overflow the item once the room
    # kept for the progress lines and the result is set aside. It is refused at create, before the write.
    absurd = _request(
        recipe_history=[
            {
                "recipe_id": 1,
                "title": secrets.token_hex(400_000),  # ~800 KB of incompressible text
                "last_cooked_at": None,
                "food_groups": [],
            }
        ]
    )
    assert stored_input_bytes(absurd) > MAX_STORED_INPUT_BYTES

    with pytest.raises(SessionTooLargeError):
        sessions.create(AgentSession(session_id="sess-big", user_sub="user-a", request=absurd), now=clock.now)

    assert sessions.get("user-a", "sess-big") is None


def test_complete_refuses_a_plan_that_would_not_fit_the_item(store: tuple[SessionStore, Clock]) -> None:
    """S2: the reserve is a check, not an assumption — the plan is measured before it is written."""
    sessions, clock = store
    near_bound = _request(
        recipe_history=[
            {"recipe_id": 1, "title": secrets.token_hex(280_000), "last_cooked_at": None, "food_groups": []}
        ]
    )
    stored = stored_input_bytes(near_bound)
    assert MAX_STORED_INPUT_BYTES - 10_000 < stored <= MAX_STORED_INPUT_BYTES
    sessions.create(AgentSession(session_id="sess-big-result", user_sub="user-a", request=near_bound), now=clock.now)
    sessions.claim("user-a", "sess-big-result", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    oversized = MealPlanResult(
        suggestions=[MealPlanSuggestion(external_id="rec_1", title="Lentil Bake", reason="r" * 90_000)]
    )

    with pytest.raises(SessionTooLargeError):
        sessions.complete("user-a", "sess-big-result", oversized, owner="attempt-1")

    record = sessions.get("user-a", "sess-big-result")
    assert record is not None
    assert record.status is SessionStatus.RUNNING
    assert record.result is None


def test_complete_stores_a_plan_inside_the_reserve(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    near_bound = _request(
        recipe_history=[
            {"recipe_id": 1, "title": secrets.token_hex(280_000), "last_cooked_at": None, "food_groups": []}
        ]
    )
    sessions.create(AgentSession(session_id="sess-ok-result", user_sub="user-a", request=near_bound), now=clock.now)
    sessions.claim("user-a", "sess-ok-result", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    fitting = MealPlanResult(
        suggestions=[MealPlanSuggestion(external_id="rec_1", title="Lentil Bake", reason="r" * 40_000)]
    )

    assert sessions.complete("user-a", "sess-ok-result", fitting, owner="attempt-1") is True

    record = sessions.get("user-a", "sess-ok-result")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.result == fitting


def test_a_queued_session_is_cancelled(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    clock.advance(seconds=30)

    assert sessions.cancel("user-a", "sess-1") is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.result is None
    assert record.error is None
    assert record.updated_at == clock.now


def test_a_running_session_is_cancelled_and_keeps_its_lease(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    assert sessions.cancel("user-a", "sess-1") is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    # Cancel is a status write and nothing else: clearing the lease would let a delivery claim it again.
    assert record.owner == "attempt-1"
    assert record.lease_until is not None


def test_cancelling_twice_changes_nothing_the_second_time(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.cancel("user-a", "sess-1")
    cancelled_at = clock.now
    clock.advance(seconds=5)

    assert sessions.cancel("user-a", "sess-1") is False

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.updated_at == cancelled_at


def test_cancelling_a_finished_session_leaves_it_done(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")

    assert sessions.cancel("user-a", "sess-1") is False

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.result == _result()


def test_cancelling_a_failed_session_leaves_it_failed(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.MODEL_ERROR), owner="attempt-1")

    assert sessions.cancel("user-a", "sess-1") is False

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)


def test_another_users_session_cannot_be_cancelled(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)

    assert sessions.cancel("user-b", "sess-1") is False

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.QUEUED


def test_cancelling_an_unknown_session_writes_nothing(store: tuple[SessionStore, Clock]) -> None:
    sessions, _clock = store

    assert sessions.cancel("user-a", "never-existed") is False
    assert sessions.get("user-a", "never-existed") is None


def test_claim_reports_a_cancelled_session_as_finished(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.cancel("user-a", "sess-1")

    outcome = sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    record = sessions.get("user-a", "sess-1")
    assert outcome is ClaimResult.FINISHED
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.owner is None


def test_cancelling_a_running_session_stops_a_takeover_resurrecting_it(store: tuple[SessionStore, Clock]) -> None:
    """A delivery that takes over a crashed run must not restart one the household cancelled."""
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.cancel("user-a", "sess-1")
    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)

    outcome = sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)

    record = sessions.get("user-a", "sess-1")
    assert outcome is ClaimResult.FINISHED
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.owner == "attempt-1"


def test_a_cancelled_session_never_becomes_done(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.cancel("user-a", "sess-1")

    assert sessions.complete("user-a", "sess-1", _result(), owner="attempt-1") is False

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.result is None


def test_a_cancelled_session_is_never_failed_afterwards(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.cancel("user-a", "sess-1")

    moved = sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED), owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert moved is False
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.error is None


def test_progress_written_after_a_cancel_is_refused(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.append_progress("user-a", "sess-1", ["Preparing"], owner="attempt-1")
    sessions.cancel("user-a", "sess-1")

    assert sessions.append_progress("user-a", "sess-1", ["Planning anyway"], owner="attempt-1") is False

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.progress == ["Preparing"]


def test_the_dead_letter_handler_leaves_a_cancelled_session_alone(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.cancel("user-a", "sess-1")
    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)

    outcome = sessions.fail_if_abandoned("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    record = sessions.get("user-a", "sess-1")
    assert outcome is AbandonResult.FINISHED
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.error is None


def test_a_full_proposal_with_alternatives_fits_the_item(store: tuple[SessionStore, Clock]) -> None:
    """V3's biggest plan, at the sizes a model really writes: the reserve has to hold it (S2's arithmetic).

    Seven meals, an alternative per card and an alternative per planned meal, each reason 1,200
    characters. If this raised `SessionTooLargeError` an accepted request would end `failed` on its last
    write instead of showing the week.
    """
    sessions, clock = store
    sessions.create(_session(meals_per_week=7), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    prose = ("A long but plausible sentence about the week, the pantry and what is going off soon. " * 16)[:1200]

    def suggestion(external_id: str, alternative: MealPlanAlternative | None) -> MealPlanSuggestion:
        return MealPlanSuggestion(
            external_id=external_id, title=f"Dish {external_id}", reason=prose, alternative=alternative
        )

    def alternative(external_id: str) -> MealPlanAlternative:
        return MealPlanAlternative(external_id=external_id, title=f"Dish {external_id}", reason=prose)

    plan = MealPlanResult(
        week_summary=prose[:400],
        suggestions=[suggestion(f"rec_{n}", alternative(f"alt_{n}")) for n in range(7)],
        planned_alternatives=[
            PlannedMealAlternative(external_id=f"planned_{n}", alternative=suggestion(f"swap_{n}", None))
            for n in range(7)
        ],
        degraded=False,
    )

    assert sessions.complete("user-a", "sess-1", plan, owner="attempt-1") is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.result == plan


# --- Swaps (V10): a swap message re-queues a finished session, one at a time -------------------------------


def _proposal() -> MealPlanResult:
    return MealPlanResult(
        suggestions=[
            MealPlanSuggestion(external_id="rec_1", title="Lentil Bake", reason="Cheap."),
            MealPlanSuggestion(external_id="rec_2", title="Tofu Noodles", reason="Quick."),
        ]
    )


def _done(sessions: SessionStore, clock: Clock, **overrides: Any) -> None:
    sessions.create(_session(**overrides), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    sessions.complete("user-a", "sess-1", _proposal(), owner="attempt-1")


def _swap(slot: str = "rec_2", note: str | None = None, week: list[str] | None = None) -> SwapMessage:
    return SwapMessage(type="swap", slot=slot, note=note, week=week or ["rec_1", "rec_2"])


def test_a_swap_requeues_a_finished_session_and_records_its_slot(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)

    swap = sessions.enqueue_swap("user-a", "sess-1", _swap(note="  maybe fish  "))

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert swap == SwapRecord(
        swap_id=1,
        slot="rec_2",
        position=1,
        note="maybe fish",
        note_use=SwapNoteUse.USED,
        queued_at=int(clock.now.timestamp()),
        week=["rec_1", "rec_2"],
    )
    assert record.status is SessionStatus.QUEUED
    assert record.pending_swap == swap
    # The proposal stays readable while the swap runs, and the finished run's lease no longer stands in the way
    # of the claim (or of failing the session if the queue never takes the message).
    assert record.result == _proposal()
    assert record.owner is None
    assert record.lease_until is None


def test_a_note_the_screen_dropped_is_recorded_but_never_stored(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)

    swap = sessions.enqueue_swap("user-a", "sess-1", _swap(), note_dropped=True)

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert swap.note is None
    assert swap.note_use is SwapNoteUse.DROPPED
    assert record.swaps == [swap]


def test_only_one_swap_runs_at_a_time(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)
    sessions.enqueue_swap("user-a", "sess-1", _swap())

    with pytest.raises(MessageRefusedError) as queued:
        sessions.enqueue_swap("user-a", "sess-1", _swap("rec_1"))
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    with pytest.raises(MessageRefusedError) as running:
        sessions.enqueue_swap("user-a", "sess-1", _swap("rec_1"))

    assert queued.value.reason is MessageRefusal.BUSY
    assert running.value.reason is MessageRefusal.BUSY
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert [swap.swap_id for swap in record.swaps] == [1]


def test_a_queued_swap_nothing_took_is_replaced_once_the_queue_would_have_taken_it(
    store: tuple[SessionStore, Clock],
) -> None:
    """The route died between storing a swap and sending it: the next swap must not be refused for a day."""
    sessions, clock = store
    _done(sessions, clock)
    lost = sessions.enqueue_swap("user-a", "sess-1", _swap())
    clock.advance(seconds=STALE_QUEUED_SWAP_SECONDS - 1)
    with pytest.raises(MessageRefusedError) as still_young:
        sessions.enqueue_swap("user-a", "sess-1", _swap("rec_1"))
    clock.advance(seconds=1)

    replacing = sessions.enqueue_swap("user-a", "sess-1", _swap("rec_1"))

    assert still_young.value.reason is MessageRefusal.BUSY
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.QUEUED
    assert record.swaps == [lost.model_copy(update={"state": SwapState.FAILED}), replacing]
    assert record.pending_swap == replacing
    assert replacing.queued_at == int(clock.now.timestamp())


def test_a_running_swap_is_never_replaced_however_old(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)
    sessions.enqueue_swap("user-a", "sess-1", _swap())
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    clock.advance(seconds=STALE_QUEUED_SWAP_SECONDS + 60)

    with pytest.raises(MessageRefusedError) as refused:
        sessions.enqueue_swap("user-a", "sess-1", _swap("rec_1"))

    assert refused.value.reason is MessageRefusal.BUSY


def test_the_stale_window_outlasts_a_receive_and_an_invocation() -> None:
    assert STALE_QUEUED_SWAP_SECONDS >= QUEUE_VISIBILITY_SECONDS + MAX_LEASE_SECONDS
    assert STALE_QUEUED_SWAP_SECONDS >= 3 * 60


def test_a_swap_before_the_proposal_exists_is_refused_as_busy(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)

    with pytest.raises(MessageRefusedError) as refused:
        sessions.enqueue_swap("user-a", "sess-1", _swap())

    assert refused.value.reason is MessageRefusal.BUSY


@pytest.mark.parametrize("ending", ["cancel", "fail"])
def test_a_session_with_no_proposal_takes_no_swap(store: tuple[SessionStore, Clock], ending: str) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    if ending == "cancel":
        sessions.cancel("user-a", "sess-1")
    else:
        sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.MODEL_ERROR), owner="attempt-1")

    with pytest.raises(MessageRefusedError) as refused:
        sessions.enqueue_swap("user-a", "sess-1", _swap())

    assert refused.value.reason is MessageRefusal.NO_PROPOSAL


def test_a_meal_already_in_the_plan_is_not_a_slot_a_swap_can_replace(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock, exclude_external_ids=["rec_planned"])

    with pytest.raises(MessageRefusedError) as refused:
        sessions.enqueue_swap("user-a", "sess-1", _swap("rec_planned"))

    assert refused.value.reason is MessageRefusal.UNKNOWN_SLOT
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.swaps == []


def test_the_slot_is_placed_by_the_week_the_app_shows(store: tuple[SessionStore, Clock]) -> None:
    """The app put the cards in the other order on screen? The week it sends says where the slot is."""
    sessions, clock = store
    _done(sessions, clock)

    swap = sessions.enqueue_swap("user-a", "sess-1", _swap("rec_2", week=["rec_2", "rec_1"]))

    assert swap.position == 0


@pytest.mark.parametrize(
    "week",
    [
        ["rec_1"],
        ["rec_1", "rec_2", "rec_3"],
        ["rec_2", "rec_2"],
        ["rec_1", "rec_invented"],
        ["rec_1", "rec_planned"],
    ],
    ids=["too_short", "too_long", "repeated", "unknown_id", "planned_meal"],
)
def test_a_week_that_does_not_match_the_proposal_is_refused(store: tuple[SessionStore, Clock], week: list[str]) -> None:
    sessions, clock = store
    _done(sessions, clock, exclude_external_ids=["rec_planned"])

    with pytest.raises(MessageRefusedError) as refused:
        sessions.enqueue_swap("user-a", "sess-1", _swap("rec_2" if "rec_2" in week else "rec_1", week=week))

    assert refused.value.reason is MessageRefusal.INVALID_WEEK
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE


def test_another_users_session_takes_no_swap(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)

    with pytest.raises(UnknownSessionError):
        sessions.enqueue_swap("user-b", "sess-1", _swap())


def test_the_owner_finishes_a_swap_with_the_new_proposal(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)
    swap = sessions.enqueue_swap("user-a", "sess-1", _swap(note="maybe fish"))
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    swapped = MealPlanResult(
        suggestions=[
            _proposal().suggestions[0],
            MealPlanSuggestion(external_id="rec_fish", title="Fish Pie", reason="You asked for fish."),
        ]
    )
    finished = swap.model_copy(update={"state": SwapState.DONE, "note_use": SwapNoteUse.USED})

    assert sessions.finish_swap("user-a", "sess-1", swapped, finished, owner="attempt-other") is False
    assert sessions.finish_swap("user-a", "sess-1", swapped, finished, owner="attempt-2") is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.result == swapped
    assert record.swaps == [finished]
    view = SessionView.from_record(record)
    assert view.swap is not None
    assert view.swap.state is SwapState.DONE
    assert view.swap.note is SwapNoteUse.USED
    assert view.swap.replacement is not None
    assert view.swap.replacement.external_id == "rec_fish"


def test_a_slot_the_app_swapped_back_still_finds_its_place(store: tuple[SessionStore, Clock]) -> None:
    """Undo swap is local, so the app can ask again about a meal the server already replaced."""
    sessions, clock = store
    _done(sessions, clock)
    swap = sessions.enqueue_swap("user-a", "sess-1", _swap())
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    swapped = MealPlanResult(
        suggestions=[
            _proposal().suggestions[0],
            MealPlanSuggestion(external_id="rec_fish", title="Fish Pie", reason="Fish."),
        ]
    )
    sessions.finish_swap(
        "user-a", "sess-1", swapped, swap.model_copy(update={"state": SwapState.DONE}), owner="attempt-2"
    )

    # The app undid the swap on its own screen, so its week shows the original meal again.
    again = sessions.enqueue_swap("user-a", "sess-1", _swap("rec_2", week=["rec_1", "rec_2"]))

    assert again.swap_id == 2
    assert again.position == 1
    assert again.week == ["rec_1", "rec_2"]


def test_a_swap_whose_worker_died_leaves_the_proposal_swappable(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)
    sessions.enqueue_swap("user-a", "sess-1", _swap())
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
    clock.advance(seconds=FULL_INVOCATION_LEASE + 1)
    sessions.fail_if_abandoned("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    view = SessionView.from_record(record)
    assert view.status is SessionStatus.FAILED
    assert view.swap is not None
    assert view.swap.state is SwapState.FAILED
    assert view.result == _proposal()

    retried = sessions.enqueue_swap("user-a", "sess-1", _swap())

    assert retried.swap_id == 2
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.QUEUED
    assert record.error is None


def test_the_swap_history_is_bounded(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    _done(sessions, clock)
    for attempt in range(MAX_SWAPS_KEPT + 3):
        swap = sessions.enqueue_swap("user-a", "sess-1", _swap())
        owner = f"attempt-swap-{attempt}"
        sessions.claim("user-a", "sess-1", owner=owner, now=clock.now, lease_seconds=FULL_INVOCATION_LEASE)
        sessions.finish_swap(
            "user-a", "sess-1", _proposal(), swap.model_copy(update={"state": SwapState.NO_REPLACEMENT}), owner=owner
        )

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert len(record.swaps) == MAX_SWAPS_KEPT
    assert record.swaps[-1].swap_id == MAX_SWAPS_KEPT + 3
