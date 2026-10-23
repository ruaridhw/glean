"""The worker's half of the async stack: ownership, crash recovery, the budget, metrics, the dead letter.

No AWS: the session stores are the in-memory store and moto's DynamoDB (built from `template.yaml`),
the model is a fake at its boundary, and both clocks are the test's.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import boto3
import pytest
from moto import mock_aws

from glean.agent import runtime, start
from glean.agent.checkpoint import in_memory_checkpointer
from glean.agent.control import AGENT_RUN_BUDGET_SECONDS
from glean.agent.deps import AgentDeps
from glean.agent.errors import model_error_for
from glean.meal_plan.schemas import CorpusMealPlanRecipe, CorpusMealPlanResponse, MealPlanRequest, MealPlanResult
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe
from glean.sessions.dynamo import DynamoSessionStore
from glean.sessions.models import AgentSession, SessionError, SessionErrorCode, SessionStatus
from glean.sessions.queue import SessionMessage
from glean.sessions.store import LEASE_SECONDS, InMemorySessionStore
from glean.worker import dlq_handler, handle_record, handler
from tests.infra.cfn import sessions_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

REGION = "eu-west-2"
TABLE_NAME = "glean-agent-sessions-test"
_CFN_ONLY = {"TableName", "TableClass", "PointInTimeRecoverySpecification", "TimeToLiveSpecification"}


class FakeClock:
    """Wall time and monotonic seconds, moved by the test."""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime(2026, 10, 22, 12, tzinfo=UTC)
        self.seconds = 0.0

    def wall(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.seconds

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)
        self.seconds += kwargs.get("seconds", 0.0) + kwargs.get("minutes", 0.0) * 60 + kwargs.get("hours", 0.0) * 3600


class RecordingQueue:
    """Stands in for SQS: records what the local consumer asked it to do."""

    def __init__(self) -> None:
        self.deleted: list[str] = []

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

    def __init__(self, *, fails_with: BaseException | None = None) -> None:
        self.calls = 0
        self._fails_with = fails_with

    def invoke(self, _feature: object, _schema: type, *, user: str, **_kwargs: object) -> CorpusMealPlanResponse:
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


def _deps(
    sessions: InMemorySessionStore,
    tmp_path: Any,
    router: PicksOneCandidate | None = None,
    clock: FakeClock | None = None,
) -> AgentDeps:
    clock = clock or FakeClock()
    return AgentDeps(
        sessions=sessions,
        checkpointer=in_memory_checkpointer(),
        llm_router=router or PicksOneCandidate(),
        corpus_factory=lambda: _corpus(tmp_path),
        clock=clock.wall,
        monotonic=clock.monotonic,
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


def _queued_store(*session_ids: str, clock: FakeClock | None = None) -> InMemorySessionStore:
    clock = clock or FakeClock()
    sessions = InMemorySessionStore(clock=clock.wall)
    for session_id in session_ids or ("sess-1",):
        sessions.create(_queued(session_id), now=clock.now)
    return sessions


def _record(session_id: str, user_sub: str = "user-a", receipt_handle: str = "receipt-1") -> dict[str, Any]:
    return {
        "body": SessionMessage(session_id=session_id, user_sub=user_sub).model_dump_json(),
        "receiptHandle": receipt_handle,
    }


class LambdaContext:
    """The few fields Powertools reads off a Lambda context."""

    function_name = "glean-agent-worker"
    memory_limit_in_mb = 256
    aws_request_id = "test-request"
    invoked_function_arn = f"arn:aws:lambda:{REGION}:000000000000:function:glean-agent-worker"
    function_version = "$LATEST"


def test_a_run_is_handed_over_once_and_the_session_ends_done(tmp_path: Any) -> None:
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    router = PicksOneCandidate()

    assert handle_record(_record("sess-1"), _deps(sessions, tmp_path, router, clock)) is True

    record = sessions.get("user-a", "sess-1")
    assert router.calls == 1
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.owner is not None


def test_a_live_duplicate_is_dropped_before_the_plan_runs(tmp_path: Any) -> None:
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    router = PicksOneCandidate()
    deps = _deps(sessions, tmp_path, router, clock)
    # A live attempt already owns the session: the same delivery arriving twice must not run it twice.
    assert start(_queued("sess-1"), _deps(sessions, tmp_path, router, clock)) is True
    sessions.create(_queued("sess-held"), now=clock.now)
    assert sessions.claim("user-a", "sess-held", owner="other-attempt", now=clock.now)
    assert handle_record(_record("sess-held"), deps) is False

    assert router.calls == 1


def test_a_crashed_run_is_resumed_from_its_checkpoint(tmp_path: Any) -> None:
    """The review's B3: a run that dies mid-graph leaves `running`, and its redelivery finishes the job."""

    class ProcessDied(BaseException):
        """What a killed Lambda looks like from inside Python: not an Exception, so nothing catches it."""

    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    dead = _deps(sessions, tmp_path, PicksOneCandidate(fails_with=ProcessDied()), clock)

    with pytest.raises(ProcessDied):
        start(_queued("sess-1"), dead)

    crashed = sessions.get("user-a", "sess-1")
    assert crashed is not None
    assert crashed.status is SessionStatus.RUNNING

    # The queue hands the message out again after the visibility timeout; by then the lease has lapsed.
    clock.advance(seconds=LEASE_SECONDS + 10)
    recovered_router = PicksOneCandidate()
    # A deployed worker reads the checkpoint from DynamoDB, so a new attempt sees the crashed one's
    # progress. Inline, that shared state is the one saver, which is why a new attempt must reuse it.
    recovered = _deps(sessions, tmp_path, recovered_router, clock)
    recovered = AgentDeps(
        sessions=recovered.sessions,
        checkpointer=dead.checkpointer,
        llm_router=recovered.llm_router,
        corpus_factory=recovered.corpus_factory,
        clock=recovered.clock,
        monotonic=recovered.monotonic,
    )

    assert handle_record(_record("sess-1"), recovered) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    # `prepare` ran before the crash and did not run again: its line appears once, and the model was
    # called once in total, by the resumed run.
    assert record.progress[0] == "Reading your pantry and the recipes we know"
    assert record.progress.count("Reading your pantry and the recipes we know") == 1
    assert recovered_router.calls == 1


def test_a_takeover_with_no_checkpoint_starts_the_run_fresh(tmp_path: Any) -> None:
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now)
    clock.advance(seconds=LEASE_SECONDS + 1)
    router = PicksOneCandidate()

    assert handle_record(_record("sess-1"), _deps(sessions, tmp_path, router, clock)) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.progress[0] == "Reading your pantry and the recipes we know"
    assert router.calls == 1


def test_a_run_that_spends_its_budget_ends_failed_with_a_code(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """S1: the 90 s budget is enforced, so a slow run ends itself instead of being killed by the Lambda."""
    monkeypatch.setattr(runtime, "metrics", MetricsRecorder())
    clock = FakeClock()
    sessions = _queued_store(clock=clock)

    class SlowModel(PicksOneCandidate):
        def invoke(self, feature: object, schema: type, *, user: str, **kwargs: object) -> CorpusMealPlanResponse:
            # The provider takes longer than the budget it was given: it cannot, so the deadline check
            # between steps is what turns this into a typed failure at the next step.
            clock.advance(seconds=AGENT_RUN_BUDGET_SECONDS + 1)
            return super().invoke(feature, schema, user=user, **kwargs)

    handle_record(_record("sess-1"), _deps(sessions, tmp_path, SlowModel(), clock))

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert clock.seconds > AGENT_RUN_BUDGET_SECONDS
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)


def test_the_model_is_given_what_is_left_of_the_budget(tmp_path: Any) -> None:
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    seen: list[int | None] = []

    class RecordingModel(PicksOneCandidate):
        def invoke(self, feature: object, schema: type, *, user: str, **kwargs: Any) -> CorpusMealPlanResponse:
            seen.append(kwargs.get("timeout_ms"))
            return super().invoke(feature, schema, user=user, **kwargs)

    deps = _deps(sessions, tmp_path, RecordingModel(), clock)

    def slow_corpus() -> RecipeCorpusStore:
        # Preparing the candidates took 30 s of the 90, so the model may use the 60 that are left.
        clock.advance(seconds=30)
        return _corpus(tmp_path)

    deps = AgentDeps(
        sessions=deps.sessions,
        checkpointer=deps.checkpointer,
        llm_router=deps.llm_router,
        corpus_factory=slow_corpus,
        clock=deps.clock,
        monotonic=deps.monotonic,
    )

    handle_record(_record("sess-1"), deps)

    assert seen == [60_000]


def test_a_poison_message_is_dropped() -> None:
    assert handle_record({"body": "not a session message", "receiptHandle": "r"}, None) is False  # type: ignore[arg-type]


def test_a_message_for_a_session_that_is_not_in_the_table_is_dropped(tmp_path: Any) -> None:
    router = PicksOneCandidate()

    dropped = handle_record(_record("missing"), _deps(_queued_store(), tmp_path, router))

    assert dropped is False
    assert router.calls == 0


def test_a_claim_that_fails_for_another_reason_is_raised_so_the_message_is_retried(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anything but a live owner (or a finished session) must reach SQS as a failed delivery.

    Lambda only retries (and finally dead-letters) a message whose handler raises, so a store error that
    was swallowed would lose the session silently.
    """
    sessions = _queued_store()

    def broken_claim(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("DynamoDB is not answering")

    monkeypatch.setattr(sessions, "claim", broken_claim)

    with pytest.raises(RuntimeError, match="DynamoDB is not answering"):
        handle_record(_record("sess-1"), _deps(sessions, tmp_path))


def test_a_model_failure_ends_the_session_with_its_code(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runtime, "metrics", MetricsRecorder())
    sessions = _queued_store()

    handle_record(_record("sess-1"), _deps(sessions, tmp_path, PicksOneCandidate(fails_with=RuntimeError("boom"))))

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)


def test_every_attempt_is_counted_in_cloudwatch_including_its_wall_time(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = MetricsRecorder()
    monkeypatch.setattr(runtime, "metrics", recorder)
    sessions = _queued_store("sess-1", "sess-fail")

    handle_record(_record("sess-1"), _deps(sessions, tmp_path))
    doomed = PicksOneCandidate(fails_with=RuntimeError("boom"))
    handle_record(_record("sess-fail"), _deps(sessions, tmp_path, doomed))

    assert recorder.names == [
        "SessionsStarted",
        "SessionsCompleted",
        "SessionWallTime",
        "SessionsStarted",
        "SessionsFailed",
        "SessionWallTime",
    ]
    assert all(value >= 0 for value in recorder.values[2::3])


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
    sessions_table.claim("user-a", "sess-1", owner="attempt-1", now=datetime.now(UTC))
    sessions_table.complete("user-a", "sess-1", MealPlanResult(suggestions=[]), owner="attempt-1")

    dlq_handler({"Records": [_record("sess-1")]}, LambdaContext())

    record = sessions_table.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.error is None


def test_the_worker_handler_walks_every_record(monkeypatch: pytest.MonkeyPatch) -> None:
    handled: list[str] = []

    def record_it(record: dict[str, Any], _deps: object) -> bool:
        handled.append(record["body"])
        return True

    monkeypatch.setattr("glean.worker.handle_record", record_it)
    monkeypatch.setattr("glean.worker.build_deps", lambda _settings, *, llm_router=None: object())
    monkeypatch.setattr(
        "glean.worker.get_settings",
        lambda: type("Settings", (), {"agent_runner": "queue", "aws_region": REGION})(),
    )

    handler({"Records": [_record("sess-1"), _record("sess-2")]}, LambdaContext())

    assert handled == [_record("sess-1")["body"], _record("sess-2")["body"]]
