"""The worker's half of the async stack: the claim, the visibility lease, metrics and the dead letter.

No AWS: the session stores are the in-memory store and moto's DynamoDB (built from `template.yaml`),
the model is a fake at its boundary, and the clock is a number the test moves.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from glean.agent import runtime
from glean.agent.checkpoint import in_memory_checkpointer
from glean.agent.deps import AgentDeps
from glean.agent.errors import model_error_for
from glean.meal_plan.schemas import CorpusMealPlanRecipe, CorpusMealPlanResponse, MealPlanRequest, MealPlanResult
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.models import AgentSession, SessionError, SessionErrorCode, SessionStatus
from glean.sessions.queue import SessionMessage, VisibilityLease
from glean.sessions.store import InMemorySessionStore
from glean.worker import dlq_handler, handle_record, handler
from tests.infra.cfn import sessions_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

REGION = "eu-west-2"
TABLE_NAME = "glean-agent-sessions-test"
_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification", "TimeToLiveSpecification"}


class LambdaContext:
    """The few fields Powertools reads off a Lambda context."""

    function_name = "glean-agent-worker"
    memory_limit_in_mb = 256
    aws_request_id = "test-request"
    invoked_function_arn = f"arn:aws:lambda:{REGION}:000000000000:function:glean-agent-worker"
    function_version = "$LATEST"


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class RecordingQueue:
    """Stands in for SQS: records what the worker asked it to do."""

    def __init__(self) -> None:
        self.visibility: list[tuple[str, int]] = []
        self.deleted: list[str] = []

    def extend_visibility(self, receipt_handle: str, seconds: int = 60) -> None:
        self.visibility.append((receipt_handle, seconds))

    def delete(self, receipt_handle: str) -> None:
        self.deleted.append(receipt_handle)


class MetricsRecorder:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.values: list[Any] = []

    def add_metric(self, *, name: str, unit: object, value: object) -> None:
        self.names.append(name)
        self.values.append(value)

    def flush_metrics(self) -> None:
        return None


class PicksOneCandidate:
    """The meal-plan model at its boundary: it picks the first candidate it was offered."""

    def __init__(self, *, fails_with: Exception | None = None) -> None:
        self.calls = 0
        self._fails_with = fails_with

    def invoke(self, _feature: object, _schema: type, *, user: str, **_kwargs: object) -> CorpusMealPlanResponse:
        import json  # noqa: PLC0415 - only the fake needs the prompt's own shape

        self.calls += 1
        if self._fails_with is not None:
            raise self._fails_with
        context = json.loads(user)
        return CorpusMealPlanResponse(
            suggestions=[
                CorpusMealPlanRecipe(external_id=c["external_id"], title=c["title"], reason="Fine.")
                for c in context["candidates"][:1]
            ]
        )

    def model_id_for(self, _feature: object, **_kwargs: object) -> str:
        return "fake/model"


def _corpus(tmp_path: Any) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title in [("rec_a", "Lentil Bake"), ("rec_b", "Tofu Noodles")]:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=title.split()[0].casefold(), quantity=1, unit="each")],
            )
        )
    return corpus


def _deps(sessions: InMemorySessionStore, tmp_path: Any, router: PicksOneCandidate | None = None) -> AgentDeps:
    return AgentDeps(
        sessions=sessions,
        checkpointer=in_memory_checkpointer(),
        llm_router=router or PicksOneCandidate(),
        corpus_factory=lambda: _corpus(tmp_path),
    )


def _queued(session_id: str = "sess-1") -> AgentSession:
    return AgentSession(
        session_id=session_id,
        user_sub="user-a",
        request=MealPlanRequest(
            source="corpus",
            pantry=[],
            purchase_tolerance=0.3,
            meals_per_week=2,
            dietary_flags=[],
            max_active_time_mins=None,
        ),
    )


def _queued_store(*session_ids: str) -> InMemorySessionStore:
    sessions = InMemorySessionStore()
    for session_id in session_ids or ("sess-1",):
        sessions.create(_queued(session_id), now=datetime.now(UTC))
    return sessions


def _record(session_id: str, user_sub: str = "user-a", receipt_handle: str = "receipt-1") -> dict[str, Any]:
    return {
        "body": SessionMessage(session_id=session_id, user_sub=user_sub).model_dump_json(),
        "receiptHandle": receipt_handle,
    }


def test_the_lease_renews_on_its_interval_and_not_in_between() -> None:
    clock = Clock()
    renewals: list[int] = []
    lease = VisibilityLease(lambda seconds: renewals.append(seconds), renew_every=20, clock=clock)

    at_zero = lease.tick()
    clock.now = 19
    before_due = lease.tick()
    clock.now = 20
    at_due = lease.tick()
    clock.now = 25
    between = lease.tick()
    clock.now = 40
    at_next_due = lease.tick()

    assert (at_zero, before_due, at_due, between, at_next_due) == (False, False, True, False, True)
    assert renewals == [60, 60]


def test_the_lease_keeps_a_run_invisible_while_it_runs() -> None:
    renewals: list[int] = []
    lease = VisibilityLease(lambda seconds: renewals.append(seconds), renew_every=0.05)

    with lease.keep_alive():
        time.sleep(0.18)

    assert len(renewals) >= 2


def test_a_failed_renewal_does_not_stop_the_run() -> None:
    clock = Clock()

    def broken(_seconds: int) -> None:
        raise RuntimeError("SQS is not answering")

    lease = VisibilityLease(broken, renew_every=20, clock=clock)
    clock.now = 20

    assert lease.tick() is False


def test_a_run_is_handed_over_only_once_and_the_message_survives_it(tmp_path: Any) -> None:
    sessions = _queued_store()
    router = PicksOneCandidate()
    deps = _deps(sessions, tmp_path, router)
    queue = RecordingQueue()

    assert handle_record(_record("sess-1"), deps, queue) is True

    assert router.calls == 1
    assert sessions.get("user-a", "sess-1").status is SessionStatus.DONE
    # The first renewal is not due for 20 s, so a fast local run renews nothing.
    assert queue.visibility == []


def test_a_duplicate_delivery_is_dropped_before_the_plan_runs(tmp_path: Any) -> None:
    sessions = _queued_store()
    router = PicksOneCandidate()
    deps = _deps(sessions, tmp_path, router)

    first = handle_record(_record("sess-1"), deps, RecordingQueue())
    second = handle_record(_record("sess-1"), deps, RecordingQueue())

    assert (first, second) == (True, False)
    assert router.calls == 1


def test_a_poison_message_is_dropped() -> None:
    queue = RecordingQueue()

    assert handle_record({"body": "not a session message", "receiptHandle": "r"}, None, queue) is False  # type: ignore[arg-type]
    assert queue.visibility == []


def test_a_message_for_a_session_that_is_not_in_the_table_is_dropped(tmp_path: Any) -> None:
    router = PicksOneCandidate()

    dropped = handle_record(_record("missing"), _deps(_queued_store(), tmp_path, router), RecordingQueue())

    assert dropped is False
    assert router.calls == 0


def test_a_model_failure_ends_the_session_with_its_code(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "metrics", MetricsRecorder())
    sessions = _queued_store()
    deps = _deps(sessions, tmp_path, PicksOneCandidate(fails_with=RuntimeError("the model fell over")))

    handle_record(_record("sess-1"), deps, RecordingQueue())

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)


def test_every_run_is_counted_in_cloudwatch(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MetricsRecorder()
    monkeypatch.setattr(runtime, "metrics", recorder)
    sessions = _queued_store("sess-1", "sess-fail")

    handle_record(_record("sess-1"), _deps(sessions, tmp_path), RecordingQueue())
    doomed = PicksOneCandidate(fails_with=RuntimeError("boom"))
    handle_record(_record("sess-fail"), _deps(sessions, tmp_path, doomed), RecordingQueue())

    assert recorder.names == [
        "SessionsStarted",
        "SessionsCompleted",
        "SessionWallTime",
        "SessionsStarted",
        "SessionsFailed",
    ]
    assert recorder.values[2] >= 0


def test_a_provider_throttle_is_rate_limited_with_the_minutes_it_asked_for() -> None:
    class Throttled(Exception):
        def __init__(self, headers: dict[str, str]) -> None:
            super().__init__("429")
            self.status_code = 429
            self.response = type("Response", (), {"status_code": 429, "headers": headers})()

    assert model_error_for(Throttled({"retry-after": "120"})) == SessionError(
        code=SessionErrorCode.RATE_LIMITED, retry_after_minutes=2
    )
    assert model_error_for(Throttled({})) == SessionError(code=SessionErrorCode.RATE_LIMITED)
    assert model_error_for(RuntimeError("boom")) == SessionError(code=SessionErrorCode.MODEL_ERROR)


@pytest.fixture
def sessions_table(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoSessionStore]:
    """`agent_sessions` exactly as `template.yaml` defines it, behind moto."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        properties = {key: value for key, value in sessions_table_properties().items() if key not in _CFN_ONLY}
        dynamodb.create_table(TableName=TABLE_NAME, **properties)
        monkeypatch.setenv("AGENT_SESSIONS_TABLE", TABLE_NAME)
        monkeypatch.setenv("AWS_REGION", REGION)
        monkeypatch.delenv("DYNAMODB_ENDPOINT_URL", raising=False)
        yield DynamoSessionStore(TABLE_NAME, region=REGION)


def test_the_dead_letter_handler_marks_the_session_worker_failed(sessions_table: DynamoSessionStore) -> None:
    sessions_table.create(_queued(), now=datetime.now(UTC))

    dlq_handler({"Records": [_record("sess-1")]}, LambdaContext())

    record = sessions_table.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.WORKER_FAILED)


def test_a_dead_letter_for_a_finished_session_leaves_it_done(sessions_table: DynamoSessionStore) -> None:
    sessions_table.create(_queued(), now=datetime.now(UTC))
    sessions_table.claim("user-a", "sess-1")
    sessions_table.complete("user-a", "sess-1", MealPlanResult(suggestions=[]))

    dlq_handler({"Records": [_record("sess-1")]}, LambdaContext())

    record = sessions_table.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.error is None


def test_the_worker_handler_walks_every_record(monkeypatch: pytest.MonkeyPatch) -> None:
    handled: list[str] = []

    def record_it(record: dict[str, Any], _deps: object, _queue: object) -> bool:
        handled.append(record["body"])
        return True

    monkeypatch.setattr("glean.worker.handle_record", record_it)
    monkeypatch.setattr("glean.worker.build_deps", lambda _settings, *, queue: object())
    monkeypatch.setattr("glean.worker.session_queue", lambda _settings: object())
    monkeypatch.setattr(
        "glean.worker.get_settings",
        lambda: type("Settings", (), {"agent_runner": "queue", "aws_region": REGION})(),
    )

    handler({"Records": [_record("sess-1"), _record("sess-2")]}, LambdaContext())

    assert handled == [_record("sess-1")["body"], _record("sess-2")["body"]]
