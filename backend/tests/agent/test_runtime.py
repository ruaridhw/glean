"""The worker's half of the async stack: ownership, crash recovery, the budget, metrics, the dead letter.

No AWS: the session stores are the in-memory store and moto's DynamoDB (built from `template.yaml`),
the model is a fake at its boundary, and both clocks are the test's.
"""

from __future__ import annotations

import json
import secrets
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
from glean.sessions.models import (
    ITEM_OVERHEAD_BYTES,
    MAX_ITEM_BYTES,
    MAX_STORED_INPUT_BYTES,
    AgentSession,
    SessionError,
    SessionErrorCode,
    SessionStatus,
    stored_input_bytes,
)
from glean.sessions.queue import SessionMessage
from glean.sessions.store import (
    DEAD_LETTER_VISIBILITY_SECONDS,
    MAX_LEASE_SECONDS,
    QUEUE_VISIBILITY_SECONDS,
    WORKER_TIMEOUT_SECONDS,
    InMemorySessionStore,
    SessionBusyError,
    lease_seconds_for,
)
from glean.worker import dlq_handler, handle_record, handler
from tests.infra.cfn import sessions_table_properties

if TYPE_CHECKING:
    from collections.abc import Iterator

REGION = "eu-west-2"
TABLE_NAME = "glean-agent-sessions-test"
SOURCE_QUEUE_NAME = "glean-agent-sessions-test"
DLE_QUEUE_NAME = "glean-agent-sessions-dlq-test"
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


class CancelsWhilePlanning(PicksOneCandidate):
    """The household taps Cancel while the model is choosing: the DELETE lands mid-run."""

    def __init__(self, sessions: InMemorySessionStore) -> None:
        super().__init__()
        self._sessions = sessions

    def invoke(self, _feature: object, _schema: type, *, user: str, **kwargs: object) -> CorpusMealPlanResponse:
        self._sessions.cancel("user-a", "sess-1")
        return super().invoke(_feature, _schema, user=user, **kwargs)


class _CancelOnComplete(InMemorySessionStore):
    """A store where the household's DELETE lands just before the plan write."""

    def complete(self, user_sub: str, session_id: str, result: Any, *, owner: str) -> bool:
        self.cancel(user_sub, session_id)
        return super().complete(user_sub, session_id, result, owner=owner)


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
    *,
    remaining_seconds: float = WORKER_TIMEOUT_SECONDS,
) -> AgentDeps:
    clock = clock or FakeClock()
    return AgentDeps(
        sessions=sessions,
        checkpointer=in_memory_checkpointer(),
        llm_router=router or PicksOneCandidate(),
        corpus_factory=lambda: _corpus(tmp_path),
        clock=clock.wall,
        monotonic=clock.monotonic,
        remaining_seconds=lambda: remaining_seconds,
    )


def _with(
    deps: AgentDeps,
    *,
    checkpointer: Any = None,
    corpus_factory: Any = None,
    remaining_seconds: float | None = None,
) -> AgentDeps:
    """The same deps with one field replaced (the dataclass is frozen)."""
    return AgentDeps(
        sessions=deps.sessions,
        checkpointer=checkpointer or deps.checkpointer,
        llm_router=deps.llm_router,
        corpus_factory=corpus_factory or deps.corpus_factory,
        clock=deps.clock,
        monotonic=deps.monotonic,
        remaining_seconds=(lambda: remaining_seconds) if remaining_seconds is not None else deps.remaining_seconds,
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

    def get_remaining_time_in_millis(self) -> int:
        """What the worker anchors its lease to: a full invocation's worth."""
        return WORKER_TIMEOUT_SECONDS * 1000


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


def test_a_live_duplicate_is_failed_not_acknowledged(tmp_path: Any) -> None:
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    router = PicksOneCandidate()
    deps = _deps(sessions, tmp_path, router, clock)
    # A live attempt already owns the session: the same delivery arriving twice must not run it twice.
    assert start(_queued("sess-1"), _deps(sessions, tmp_path, router, clock)) is True
    sessions.create(_queued("sess-held"), now=clock.now)
    sessions.claim(
        "user-a",
        "sess-held",
        owner="other-attempt",
        now=clock.now,
        lease_seconds=lease_seconds_for(WORKER_TIMEOUT_SECONDS),
    )

    with pytest.raises(SessionBusyError):
        handle_record(_record("sess-held"), deps)

    assert router.calls == 1
    assert sessions.get("user-a", "sess-held").status is SessionStatus.RUNNING


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
    clock.advance(seconds=MAX_LEASE_SECONDS + 10)
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


def test_a_run_that_crashes_late_is_taken_over_at_the_visibility_boundary(tmp_path: Any) -> None:
    """The round-2 reproduction: a crash after a long prepare must not leave the retry with a live lease.

    The lease is fixed at claim, so a redelivery at the queue's visibility boundary (130 s) always finds it
    lapsed (125 s) and takes over. With a refreshed lease it would have read "owned elsewhere", been acked,
    and the session would have stayed running for ever.
    """

    class ProcessDied(BaseException):
        """A killed Lambda: not an Exception, so nothing catches it."""

    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    dead = _deps(sessions, tmp_path, PicksOneCandidate(fails_with=ProcessDied()), clock)
    claimed_lease = int(clock.now.timestamp()) + lease_seconds_for(WORKER_TIMEOUT_SECONDS)

    def slow_prepare() -> RecipeCorpusStore:
        corpora = _corpus(tmp_path)
        clock.advance(seconds=45)  # a slow corpus read, past the old 40 s refresh point
        return corpora

    dead = AgentDeps(
        sessions=dead.sessions,
        checkpointer=dead.checkpointer,
        llm_router=dead.llm_router,
        corpus_factory=slow_prepare,
        clock=dead.clock,
        monotonic=dead.monotonic,
    )

    with pytest.raises(ProcessDied):
        start(_queued("sess-1"), dead)

    crashed = sessions.get("user-a", "sess-1")
    assert crashed is not None
    assert crashed.status is SessionStatus.RUNNING
    assert crashed.lease_until == claimed_lease

    # The message reappears when the queue's visibility timeout expires, which is after the lease lapsed.
    clock.advance(seconds=QUEUE_VISIBILITY_SECONDS - 45)
    recovered_router = PicksOneCandidate()
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
    assert record.progress.count("Reading your pantry and the recipes we know") == 1
    assert recovered_router.calls == 1


def test_a_run_writes_no_lease_beyond_the_claim(tmp_path: Any) -> None:
    """Refreshes are gone: a completed run costs create, claim, three progress lines and the result."""
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    writes_after_create = sessions.writes
    claimed_at = int(clock.now.timestamp())

    def slow_corpus() -> RecipeCorpusStore:
        clock.advance(seconds=50)  # well past the old refresh cadence
        return _corpus(tmp_path)

    deps = _deps(sessions, tmp_path, PicksOneCandidate(), clock)
    deps = AgentDeps(
        sessions=deps.sessions,
        checkpointer=deps.checkpointer,
        llm_router=deps.llm_router,
        corpus_factory=slow_corpus,
        clock=deps.clock,
        monotonic=deps.monotonic,
    )

    handle_record(_record("sess-1"), deps)

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.lease_until == claimed_at + lease_seconds_for(WORKER_TIMEOUT_SECONDS)
    # claim + three progress writes + complete; no lease refresh anywhere in between.
    assert sessions.writes - writes_after_create == 5


def test_a_crash_before_the_session_write_publishes_the_saved_plan(tmp_path: Any) -> None:
    """Round 2's S1: the graph finished, only the session write was lost, so the retry publishes that plan.

    Re-running here would bill a second model call for a plan the checkpoint already holds — and could turn
    a finished plan into a model error if the provider fails the second time.
    """

    class ProcessDied(BaseException):
        """The process vanished between the last node and the session write."""

    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    router = PicksOneCandidate()
    deps = _deps(sessions, tmp_path, router, clock)

    publish_attempts = {"count": 0}
    real_complete = sessions.complete

    def die_on_first_publish(*args: Any, **kwargs: Any) -> bool:
        publish_attempts["count"] += 1
        if publish_attempts["count"] == 1:
            raise ProcessDied
        return real_complete(*args, **kwargs)

    sessions.complete = die_on_first_publish  # ty: ignore[invalid-assignment]

    with pytest.raises(ProcessDied):
        start(_queued("sess-1"), deps)

    crashed = sessions.get("user-a", "sess-1")
    assert crashed is not None
    assert crashed.status is SessionStatus.RUNNING
    assert router.calls == 1

    clock.advance(seconds=QUEUE_VISIBILITY_SECONDS)
    recovered = _deps(sessions, tmp_path, router, clock)
    recovered = AgentDeps(
        sessions=recovered.sessions,
        checkpointer=deps.checkpointer,
        llm_router=recovered.llm_router,
        corpus_factory=recovered.corpus_factory,
        clock=recovered.clock,
        monotonic=recovered.monotonic,
    )

    assert handle_record(_record("sess-1"), recovered) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.error is None
    # No second model call, and prepare did not run again: the finished plan was published as it stood.
    assert router.calls == 1
    assert record.progress.count("Reading your pantry and the recipes we know") == 1
    assert isinstance(record.result, MealPlanResult)
    assert len(record.result.suggestions) == 1


def test_a_takeover_with_no_checkpoint_starts_the_run_fresh(tmp_path: Any) -> None:
    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    sessions.claim(
        "user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=lease_seconds_for(WORKER_TIMEOUT_SECONDS)
    )
    clock.advance(seconds=MAX_LEASE_SECONDS + 1)
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


def _near_bound_request() -> MealPlanRequest:
    """An input that is accepted and leaves almost none of the item's room to the outcome.

    The title is incompressible, so the gzipped inputs land just under the bound rather than at a few KB.
    """
    return MealPlanRequest(
        source="corpus",
        pantry=[],
        purchase_tolerance=0.3,
        meals_per_week=2,
        dietary_flags=[],
        max_active_time_mins=None,
        recipe_history=[
            {"recipe_id": 1, "title": secrets.token_hex(280_000), "last_cooked_at": None, "food_groups": []}
        ],
    )


class _ReasonModel(PicksOneCandidate):
    """A schema-valid plan whose one reason is exactly *reason_bytes* characters."""

    def __init__(self, reason_bytes: int) -> None:
        super().__init__()
        self._reason_bytes = reason_bytes

    def invoke(self, feature: object, schema: type, *, user: str, **kwargs: Any) -> CorpusMealPlanResponse:
        context = json.loads(user)
        return CorpusMealPlanResponse(
            suggestions=[
                CorpusMealPlanRecipe(
                    external_id=context["candidates"][0]["external_id"],
                    title=context["candidates"][0]["title"],
                    reason=secrets.token_hex(self._reason_bytes // 2),
                )
            ]
        )


def test_a_plan_that_would_not_fit_the_item_fails_the_session_instead_of_raising(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 2's S2: the reserve is enforced, not assumed.

    Near-bound inputs plus a schema-valid plan larger than the reserve exceed one item. The run must end
    `failed / model_error` — a typed outcome the app can act on — rather than raising into SQS (which would
    dead-letter it after two attempts and leave the household with nothing).
    """
    monkeypatch.setattr(runtime, "metrics", MetricsRecorder())
    clock = FakeClock()
    sessions = InMemorySessionStore(clock=clock.wall)
    request = _near_bound_request()
    stored = stored_input_bytes(request)
    assert MAX_STORED_INPUT_BYTES - 10_000 < stored <= MAX_STORED_INPUT_BYTES
    sessions.create(AgentSession(session_id="sess-1", user_sub="user-a", request=request), now=clock.now)
    # 90 KB of plan against ~10 KB of remaining room: over the item limit.
    assert stored + 90_000 + ITEM_OVERHEAD_BYTES > MAX_ITEM_BYTES

    handle_record(_record("sess-1"), _deps(sessions, tmp_path, _ReasonModel(90_000), clock))

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.MODEL_ERROR)
    assert record.result is None


def test_a_plan_that_just_fits_is_written(tmp_path: Any) -> None:
    """The other side of the boundary: the same inputs plus a plan inside the reserve are stored."""
    clock = FakeClock()
    sessions = InMemorySessionStore(clock=clock.wall)
    request = _near_bound_request()
    stored = stored_input_bytes(request)
    sessions.create(AgentSession(session_id="sess-1", user_sub="user-a", request=request), now=clock.now)
    assert stored + 40_000 + ITEM_OVERHEAD_BYTES < MAX_ITEM_BYTES

    handle_record(_record("sess-1"), _deps(sessions, tmp_path, _ReasonModel(40_000), clock))

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.result is not None
    assert len(record.result.suggestions) == 1
    assert len(record.result.suggestions[0].reason) == 40_000


def test_a_late_claim_still_lets_the_redelivery_take_over(tmp_path: Any) -> None:
    """Round 3's path A: the claim happens seconds after the receive, so the lease must follow the deadline.

    Claiming 10 s into the invocation leaves 110 s, so the lease ends at claim + 112 — before the message
    reappears at receive + 150. A lease measured as a constant from claim time would still have been live.
    """

    class ProcessDied(BaseException):
        """A killed Lambda: not an Exception, so nothing catches it."""

    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    # 10 s of init, imports and the first reads before the claim.
    slow_deps = _deps(
        sessions,
        tmp_path,
        PicksOneCandidate(fails_with=ProcessDied()),
        clock,
        remaining_seconds=WORKER_TIMEOUT_SECONDS - 10,
    )

    received_at = int(clock.now.timestamp())
    with pytest.raises(ProcessDied):
        start(_queued("sess-1"), slow_deps)

    crashed = sessions.get("user-a", "sess-1")
    assert crashed is not None
    assert crashed.lease_until == received_at + lease_seconds_for(WORKER_TIMEOUT_SECONDS - 10)
    assert crashed.lease_until < received_at + QUEUE_VISIBILITY_SECONDS

    # The queue hands the message out again once the visibility lapses, after the lease has.
    clock.advance(seconds=QUEUE_VISIBILITY_SECONDS)
    recovered_router = PicksOneCandidate()
    recovered = _with(_deps(sessions, tmp_path, recovered_router, clock), checkpointer=slow_deps.checkpointer)

    assert handle_record(_record("sess-1"), recovered) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert record.progress.count("Reading your pantry and the recipes we know") == 1


def test_a_live_duplicate_is_failed_so_the_message_survives_then_recovers(tmp_path: Any) -> None:
    """Round 3's path B: acknowledging a duplicate would delete the logical message the live run needs.

    Here the duplicate's delivery is failed (no ack), the live run then dies, and the message that is still
    on the queue is what recovers the session.
    """

    clock = FakeClock()
    sessions = _queued_store(clock=clock)
    live_lease = lease_seconds_for(WORKER_TIMEOUT_SECONDS)
    sessions.claim("user-a", "sess-1", owner="attempt-1", now=clock.now, lease_seconds=live_lease)
    duplicate = _deps(sessions, tmp_path, PicksOneCandidate(), clock)

    # The duplicate delivery is refused: raising is what makes Lambda keep (not delete) the message.
    with pytest.raises(SessionBusyError):
        handle_record(_record("sess-1"), duplicate)
    assert sessions.get("user-a", "sess-1").status is SessionStatus.RUNNING

    # The live attempt dies without writing anything. Its message comes back after the visibility timeout.
    clock.advance(seconds=QUEUE_VISIBILITY_SECONDS)
    recovered_router = PicksOneCandidate()
    recovered = _deps(sessions, tmp_path, recovered_router, clock)

    assert handle_record(_record("sess-1"), recovered) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.DONE
    assert recovered_router.calls == 1


def test_the_dead_letter_handler_keeps_a_dead_letter_for_a_live_run(sessions_table: DynamoSessionStore) -> None:
    """A dead letter that finds its run still working must be kept, not acknowledged.

    Returning success would delete the last recovery trigger: if the live owner then died, nothing
    would be left to fail or resume the session. So the handler raises, the dead-letter queue's own
    visibility timeout brings it back, and by then the run is finished or its lease has lapsed.
    """
    sessions_table.create(_queued(), now=datetime.now(UTC))
    sessions_table.claim("user-a", "sess-1", owner="attempt-1", now=datetime.now(UTC), lease_seconds=MAX_LEASE_SECONDS)

    with pytest.raises(SessionBusyError):
        dlq_handler({"Records": [_record("sess-1")]}, LambdaContext())

    record = sessions_table.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.RUNNING
    assert record.error is None


def test_the_dead_letter_handler_fails_the_session_once_its_lease_has_lapsed(
    sessions_table: DynamoSessionStore,
) -> None:
    """The retry after the live owner died: now the session is abandoned and becomes worker_failed."""
    sessions_table.create(_queued(), now=datetime.now(UTC))
    sessions_table.claim(
        "user-a",
        "sess-1",
        owner="attempt-1",
        now=datetime.now(UTC) - timedelta(seconds=MAX_LEASE_SECONDS + 1),
        lease_seconds=MAX_LEASE_SECONDS,
    )

    dlq_handler({"Records": [_record("sess-1")]}, LambdaContext())

    record = sessions_table.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error == SessionError(code=SessionErrorCode.WORKER_FAILED)


def test_a_dead_letter_kept_for_a_live_run_is_failed_when_that_run_dies(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 4's reproduction, with the real queues, redrive and both Lambda entry points.

    Duplicate deliveries of one message each fail on purpose (a live owner), which spends the source
    queue's receive budget and redrives the logical message to the dead-letter queue. The dead-letter
    handler finds that owner still live, so it raises rather than acknowledge — returning would delete
    the last trigger that can recover the session. The owner then dies, and the next dead-letter
    delivery, after the lease lapses, marks the session `worker_failed`.
    """
    clock = FakeClock()
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        dynamodb.create_table(
            TableName=TABLE_NAME,
            **{key: value for key, value in sessions_table_properties().items() if key not in _CFN_ONLY},
        )
        sessions = DynamoSessionStore(TABLE_NAME, region=REGION, clock=clock.wall)
        sqs = boto3.client("sqs", region_name=REGION)
        dead_letter_url = sqs.create_queue(
            QueueName=DLE_QUEUE_NAME,
            Attributes={"VisibilityTimeout": str(DEAD_LETTER_VISIBILITY_SECONDS), "MessageRetentionPeriod": "1209600"},
        )["QueueUrl"]
        dead_letter_arn = sqs.get_queue_attributes(QueueUrl=dead_letter_url, AttributeNames=["QueueArn"])["Attributes"][
            "QueueArn"
        ]
        source_url = sqs.create_queue(
            QueueName=SOURCE_QUEUE_NAME,
            Attributes={
                "VisibilityTimeout": str(QUEUE_VISIBILITY_SECONDS),
                "RedrivePolicy": json.dumps({"deadLetterTargetArn": dead_letter_arn, "maxReceiveCount": "3"}),
            },
        )["QueueUrl"]

        worker_deps = AgentDeps(
            sessions=sessions,
            checkpointer=in_memory_checkpointer(),
            llm_router=PicksOneCandidate(),
            corpus_factory=lambda: _corpus(tmp_path),
            clock=clock.wall,
            monotonic=clock.monotonic,
            remaining_seconds=lambda: WORKER_TIMEOUT_SECONDS,
        )
        monkeypatch.setattr("glean.worker.get_settings", lambda: type("Settings", (), {})())
        monkeypatch.setattr("glean.worker.build_deps", lambda _settings, *, remaining_seconds=None: worker_deps)
        # The DLQ handler builds its own store from the environment; give it the moto table and this clock.
        monkeypatch.setattr("glean.worker.DynamoSessionStore.from_environment", lambda: sessions)

        sessions.create(_queued(), now=clock.now)
        sqs.send_message(
            QueueUrl=source_url,
            MessageBody=SessionMessage(session_id="sess-1", user_sub="user-a").model_dump_json(),
        )

        # Delivery 1 starts the owner, whose lease covers its whole invocation.
        first = sqs.receive_message(QueueUrl=source_url, MaxNumberOfMessages=1, WaitTimeSeconds=0)["Messages"][0]
        sessions.claim("user-a", "sess-1", owner="owner-a", now=clock.now, lease_seconds=MAX_LEASE_SECONDS)

        # Deliveries 2 and 3 are duplicates that arrive while the owner is alive. Each fails, so neither
        # is acknowledged, and together they use up the source queue's receive budget.
        receipt = first["ReceiptHandle"]
        for _ in range(2):
            sqs.change_message_visibility(QueueUrl=source_url, ReceiptHandle=receipt, VisibilityTimeout=0)
            duplicate = sqs.receive_message(QueueUrl=source_url, MaxNumberOfMessages=1, WaitTimeSeconds=0)["Messages"][
                0
            ]
            with pytest.raises(SessionBusyError):
                handler(
                    {"Records": [{"body": duplicate["Body"], "receiptHandle": duplicate["ReceiptHandle"]}]},
                    LambdaContext(),
                )
            receipt = duplicate["ReceiptHandle"]

        # The budget is spent, so the source queue redrives the logical message to the dead-letter queue.
        sqs.change_message_visibility(QueueUrl=source_url, ReceiptHandle=receipt, VisibilityTimeout=0)
        assert "Messages" not in sqs.receive_message(QueueUrl=source_url, MaxNumberOfMessages=1, WaitTimeSeconds=0)
        dead = sqs.receive_message(QueueUrl=dead_letter_url, MaxNumberOfMessages=1, WaitTimeSeconds=0)["Messages"][0]

        # The owner is still working, so the dead letter is kept: raising is what stops Lambda deleting it.
        with pytest.raises(SessionBusyError):
            dlq_handler({"Records": [{"body": dead["Body"], "receiptHandle": dead["ReceiptHandle"]}]}, LambdaContext())
        running = sessions.get("user-a", "sess-1")
        assert running is not None
        assert running.status is SessionStatus.RUNNING

        # The owner dies without writing anything; once its lease has lapsed the retried dead letter fails it.
        clock.advance(seconds=MAX_LEASE_SECONDS + 1)
        sqs.change_message_visibility(
            QueueUrl=dead_letter_url, ReceiptHandle=dead["ReceiptHandle"], VisibilityTimeout=0
        )
        retried = sqs.receive_message(QueueUrl=dead_letter_url, MaxNumberOfMessages=1, WaitTimeSeconds=0)["Messages"][0]
        dlq_handler(
            {"Records": [{"body": retried["Body"], "receiptHandle": retried["ReceiptHandle"]}]}, LambdaContext()
        )

        record = sessions.get("user-a", "sess-1")
        assert record is not None
        assert record.status is SessionStatus.FAILED
        assert record.error == SessionError(code=SessionErrorCode.WORKER_FAILED)


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
    sessions_table.claim("user-a", "sess-1", owner="attempt-1", now=datetime.now(UTC), lease_seconds=MAX_LEASE_SECONDS)
    sessions_table.complete("user-a", "sess-1", MealPlanResult(suggestions=[]), owner="attempt-1")

    # A finished session needs nothing, so its dead letter is acknowledged and leaves it alone.
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
    monkeypatch.setattr(
        "glean.worker.build_deps", lambda _settings, *, llm_router=None, remaining_seconds=None: object()
    )
    monkeypatch.setattr(
        "glean.worker.get_settings",
        lambda: type("Settings", (), {"agent_runner": "queue", "aws_region": REGION})(),
    )

    handler({"Records": [_record("sess-1"), _record("sess-2")]}, LambdaContext())

    assert handled == [_record("sess-1")["body"], _record("sess-2")["body"]]


def test_a_cancel_mid_run_stops_the_worker_between_steps(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = MetricsRecorder()
    monkeypatch.setattr(runtime, "metrics", recorder)
    sessions = _queued_store()
    deps = _deps(sessions, tmp_path, CancelsWhilePlanning(sessions))

    assert handle_record(_record("sess-1"), deps) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.result is None
    # The cancel landed while the model was choosing, so `finalise`'s progress write was refused: the run
    # stopped at the next step and wrote nothing more.
    assert len(record.progress) == 2
    assert "SessionsCancelled" in recorder.names
    assert "SessionsCompleted" not in recorder.names


def test_a_message_for_a_cancelled_session_is_acknowledged_and_runs_nothing(tmp_path: Any) -> None:
    """`claim` reports a cancelled session as FINISHED: the delivery is acked and the model is not called."""
    sessions = _queued_store()
    sessions.cancel("user-a", "sess-1")
    router = PicksOneCandidate()

    assert handle_record(_record("sess-1"), _deps(sessions, tmp_path, router)) is False

    assert router.calls == 0
    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED


def test_a_run_whose_cancel_beats_the_plan_leaves_the_session_cancelled(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The DELETE lands between the `finalise` node and the plan write: the household's cancel wins."""
    recorder = MetricsRecorder()
    monkeypatch.setattr(runtime, "metrics", recorder)
    clock = FakeClock()
    sessions = _CancelOnComplete(clock=clock.wall)
    sessions.create(_queued(), now=clock.now)
    deps = _deps(sessions, tmp_path, clock=clock)

    assert handle_record(_record("sess-1"), deps) is True

    record = sessions.get("user-a", "sess-1")
    assert record is not None
    assert record.status is SessionStatus.CANCELLED
    assert record.result is None
    assert "SessionsCancelled" in recorder.names
    assert "SessionsCompleted" not in recorder.names
