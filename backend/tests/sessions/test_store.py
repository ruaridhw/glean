"""The session store contract, run against the in-memory store and against DynamoDB (moto).

The DynamoDB table is built from `template.yaml`'s own properties, so a property the stack needs and
the tests do not set -- or the other way round -- fails here rather than at deploy time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from glean.meal_plan.schemas import MealPlanRequest, MealPlanResult, MealPlanSuggestion
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.models import (
    MAX_PROGRESS_LINES,
    SESSION_TTL_HOURS,
    AgentSession,
    ClaimResult,
    SessionError,
    SessionErrorCode,
    SessionStatus,
)
from glean.sessions.store import (
    LEASE_SECONDS,
    InMemorySessionStore,
    UnknownSessionError,
)
from tests.infra.cfn import sessions_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

    from glean.sessions.store import SessionStore

TABLE_NAME = "glean-agent-sessions-test"
REGION = "eu-west-2"
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


def _session(session_id: str = "sess-1", user_sub: str = "user-a") -> AgentSession:
    return AgentSession(session_id=session_id, user_sub=user_sub, request=_request())


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


def test_a_session_expires_a_day_after_its_last_update(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store

    sessions.create(_session(), now=clock.now)
    first = sessions.get("user-a", "sess-1")
    clock.advance(hours=6)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
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
        sessions.claim("user-b", "sess-1", owner="attempt-1", now=clock.now)
    assert sessions.get("user-a", "sess-1").status is SessionStatus.QUEUED


def test_claiming_a_queued_session_wins_once_and_a_live_duplicate_is_told_so(
    store: tuple[SessionStore, Clock],
) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)

    first = sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    duplicate = sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now)

    assert (first, duplicate) == (ClaimResult.STARTED, ClaimResult.OWNED_ELSEWHERE)
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert (record.status, record.owner) == (SessionStatus.RUNNING, "attempt-1")
    assert record.lease_until == int(clock.now.timestamp()) + LEASE_SECONDS


def test_a_claim_after_the_lease_lapsed_takes_the_session_over(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    clock.advance(seconds=LEASE_SECONDS + 1)

    takeover = sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now)

    assert takeover is ClaimResult.RESUMED
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.owner == "attempt-2"


def test_a_finished_session_cannot_be_claimed_again(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")

    assert sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now) is ClaimResult.FINISHED
    record = sessions.get("user-a", "sess-1")
    assert record.status is SessionStatus.DONE
    assert record.result == _result()


def test_a_running_attempt_renews_its_own_lease_only(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    clock.advance(seconds=LEASE_SECONDS // 2)

    mine = sessions.refresh_lease("user-a", "sess-1", owner="attempt-1", now=clock.now)
    theirs = sessions.refresh_lease("user-a", "sess-1", owner="attempt-2", now=clock.now)

    record = sessions.get("user-a", "sess-1")
    assert (mine, theirs) == (True, False)
    assert record.lease_until == int(clock.now.timestamp()) + LEASE_SECONDS


def test_an_attempt_that_lost_the_lease_cannot_write_the_outcome(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    clock.advance(seconds=LEASE_SECONDS + 1)
    sessions.claim("user-a", "sess-1", owner="attempt-2", now=clock.now)

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
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    sessions.append_progress("user-a", "sess-1", ["Preparing", "Planning", "Finishing"], owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert record.next_cursor == 3
    assert record.with_lines_since(0) == (["Preparing", "Planning", "Finishing"], 3)
    assert record.with_lines_since(2) == (["Finishing"], 3)
    assert record.with_lines_since(3) == ([], 3)


def test_the_progress_list_is_bounded_and_older_lines_drop_out(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
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
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)

    moved = sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.MODEL_ERROR), owner="attempt-1")

    record = sessions.get("user-a", "sess-1")
    assert moved is True
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)
    assert record.result is None


def test_a_rate_limited_failure_carries_its_wait(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)

    sessions.fail(
        "user-a",
        "sess-1",
        SessionError(code=SessionErrorCode.RATE_LIMITED, retry_after_minutes=12),
        owner="attempt-1",
    )

    assert sessions.get("user-a", "sess-1").error == SessionError(
        code=SessionErrorCode.RATE_LIMITED, retry_after_minutes=12
    )


def test_the_dead_letter_handler_fails_a_session_without_owning_it(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)

    moved = sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    assert moved is True
    assert sessions.get("user-a", "sess-1").status is SessionStatus.FAILED


def test_a_finished_session_is_never_failed_afterwards(store: tuple[SessionStore, Clock]) -> None:
    sessions, clock = store
    sessions.create(_session(), now=clock.now)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    sessions.complete("user-a", "sess-1", _result(), owner="attempt-1")

    moved = sessions.fail("user-a", "sess-1", SessionError(code=SessionErrorCode.WORKER_FAILED))

    record = sessions.get("user-a", "sess-1")
    assert moved is False
    assert record.status is SessionStatus.DONE
    assert record.error is None
