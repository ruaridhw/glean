"""Agent sessions end to end through the HTTP routes, with the inline runner.

Everything real runs: the routes, the session store, the agent module and its LangGraph graph, and
the pipeline. Only the boundaries are faked -- the model (answers from the candidates it was
offered), the recipe corpus (a temporary filesystem tree) and the clock.
"""

from __future__ import annotations

import json
import random
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import Request  # noqa: TC002 - FastAPI resolves this annotation at runtime.
from fastapi.testclient import TestClient

from glean.agent import start
from glean.agent.checkpoint import in_memory_checkpointer
from glean.agent.dependencies import get_session_dispatcher, get_session_store
from glean.agent.deps import AgentDeps
from glean.config import Settings, get_settings
from glean.dependencies import get_llm_router, verify_cognito_token
from glean.main import app
from glean.meal_plan import service
from glean.meal_plan.schemas import (
    MAX_COOKED_HISTORY_ITEMS,
    CorpusMealPlanRecipe,
    CorpusMealPlanResponse,
    MealPlanRequest,
)
from glean.recipe_api.blob_store import FilesystemBlobStore
from glean.recipes import corpus as corpus_module
from glean.recipes.corpus import RecipeCorpusStore
from glean.recipes.stored import StoredIngredient, StoredRecipe
from glean.sessions.models import SESSION_TTL_HOURS, AgentSession, SessionErrorCode, SessionStatus
from glean.sessions.store import InMemorySessionStore, ttl_from, utcnow

if TYPE_CHECKING:
    from collections.abc import Iterator

MEALS = 3


def _body(**overrides: Any) -> dict[str, Any]:
    return {
        "source": "corpus",
        "pantry": [{"id": 1, "name": "coriander", "quantity": 50, "unit": "g", "urgency_score": 150.0}],
        "cooked_history": [],
        "exclude_external_ids": [],
        "purchase_tolerance": 0.3,
        "meals_per_week": MEALS,
        "local_date": "2026-04-08",
        "dietary_flags": [],
        "max_active_time_mins": None,
        **overrides,
    }


class CandidatesRouter:
    """The meal-plan model at its boundary: it picks from the candidates it was offered."""

    def __init__(self, *, limit: int | None = None, fails_with: Exception | None = None) -> None:
        self._limit = limit
        self._fails_with = fails_with
        self.calls = 0

    def invoke(self, _feature: object, _schema: type, *, user: str, **_kwargs: object) -> CorpusMealPlanResponse:
        self.calls += 1
        if self._fails_with is not None:
            raise self._fails_with
        context = json.loads(user)
        offered = context["candidates"][: self._limit or context["meals_per_week"]]
        return CorpusMealPlanResponse(
            suggestions=[
                CorpusMealPlanRecipe(external_id=c["external_id"], title=c["title"], reason="Uses pantry items well.")
                for c in offered
            ]
        )

    def model_id_for(self, _feature: object, **_kwargs: object) -> str:
        return "fake/model"


def _corpus(tmp_path) -> RecipeCorpusStore:
    corpus = RecipeCorpusStore(FilesystemBlobStore(tmp_path))
    for external_id, title, ingredients in [
        ("rec_coriander_chicken", "Coriander Chicken", ["chicken breast", "coriander"]),
        ("rec_lentil_bake", "Lentil Bake", ["lentils", "potato"]),
        ("rec_tofu_noodles", "Tofu Noodles", ["tofu", "noodles"]),
        ("rec_chickpea_curry", "Chickpea Curry", ["chickpeas", "coconut milk"]),
    ]:
        corpus.save(
            StoredRecipe(
                external_id=external_id,
                title=title,
                ingredients=[StoredIngredient(canonical_name=name, quantity=1, unit="each") for name in ingredients],
            )
        )
    return corpus


def _sign_in_as_header_user(request: Request) -> str:
    return request.headers.get("x-test-user", "user-a")


@pytest.fixture
def sessions() -> InMemorySessionStore:
    return InMemorySessionStore()


@pytest.fixture
def corpus(tmp_path, monkeypatch: pytest.MonkeyPatch) -> RecipeCorpusStore:
    store = _corpus(tmp_path)
    monkeypatch.setattr(corpus_module, "get_recipe_corpus_store", lambda: store.store)
    return store


@pytest.fixture
def router() -> CandidatesRouter:
    return CandidatesRouter()


@pytest.fixture
def api(
    sessions: InMemorySessionStore,
    router: CandidatesRouter,
    test_settings: Settings,
    corpus: RecipeCorpusStore,
) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_session_store] = lambda: sessions
    app.dependency_overrides[verify_cognito_token] = _sign_in_as_header_user
    app.dependency_overrides[get_llm_router] = lambda: router
    yield TestClient(app)
    app.dependency_overrides.clear()


def _plan_to_completion(api: TestClient, body: dict[str, Any], *, user: str = "user-a") -> dict[str, Any]:
    """POST a session with the inline runner and read the finished session back."""
    created = api.post("/meal-plan/sessions", headers={"x-test-user": user}, json=body)
    assert created.status_code == 202, created.text
    session_id = created.json()["session_id"]
    polled = api.get(f"/meal-plan/sessions/{session_id}", headers={"x-test-user": user})
    assert polled.status_code == 200
    return polled.json()


def test_a_session_runs_from_queued_to_done_with_the_plan(api: TestClient) -> None:
    view = _plan_to_completion(api, _body())

    assert view["status"] == "done"
    assert view["error"] is None
    assert len(view["result"]["suggestions"]) == MEALS
    assert {s["external_id"] for s in view["result"]["suggestions"]} <= {
        "rec_coriander_chicken",
        "rec_lentil_bake",
        "rec_tofu_noodles",
        "rec_chickpea_curry",
    }
    # The plan shape is the synchronous endpoint's, `uses_up` included.
    assert set(view["result"]["suggestions"][0]) == {
        "recipe_id",
        "external_id",
        "title",
        "reason",
        "missing_ingredients",
        "uses_up",
    }


def test_the_session_result_matches_the_synchronous_endpoint_for_the_same_seed(
    api: TestClient, router: CandidatesRouter
) -> None:
    body = _body()

    view = _plan_to_completion(api, body)
    synced = service.generate_meal_plan(
        MealPlanRequest.model_validate(body),
        llm_router=router,
        rng=random.Random(view["session_id"]),  # the graph seeds its sampler with the session id
    )

    assert view["result"] == synced.model_dump(mode="json")


def test_the_plan_tops_up_only_the_slots_that_are_free(api: TestClient) -> None:
    body = _body(exclude_external_ids=["rec_lentil_bake", "rec_tofu_noodles"])

    view = _plan_to_completion(api, body)

    planned = [s["external_id"] for s in view["result"]["suggestions"]]
    assert planned
    assert not set(planned) & {"rec_lentil_bake", "rec_tofu_noodles"}


def test_a_session_with_nothing_eligible_fails_with_no_eligible_recipes(
    api: TestClient, router: CandidatesRouter
) -> None:
    view = _plan_to_completion(
        api,
        _body(
            exclude_external_ids=["rec_coriander_chicken", "rec_lentil_bake", "rec_tofu_noodles", "rec_chickpea_curry"]
        ),
    )

    assert view["status"] == "failed"
    assert view["error"] == {"code": "no_eligible_recipes", "retry_after_minutes": None}
    assert view["result"] is None
    assert router.calls == 0


def test_a_failing_model_ends_the_session_as_model_error(api: TestClient) -> None:
    api.app.dependency_overrides[get_llm_router] = lambda: CandidatesRouter(fails_with=RuntimeError("boom"))

    view = _plan_to_completion(api, _body())

    assert view["status"] == "failed"
    assert view["error"]["code"] == "model_error"


def test_a_throttled_model_ends_the_session_rate_limited_with_the_wait(api: TestClient) -> None:
    throttle = _throttled(retry_after="120")
    api.app.dependency_overrides[get_llm_router] = lambda: CandidatesRouter(fails_with=throttle)

    view = _plan_to_completion(api, _body())

    assert view["status"] == "failed"
    assert view["error"] == {"code": "rate_limited", "retry_after_minutes": 2}


def test_another_users_session_is_not_found(api: TestClient) -> None:
    created = api.post("/meal-plan/sessions", headers={"x-test-user": "user-a"}, json=_body())
    session_id = created.json()["session_id"]

    theirs = api.get(f"/meal-plan/sessions/{session_id}", headers={"x-test-user": "user-b"})
    mine = api.get(f"/meal-plan/sessions/{session_id}", headers={"x-test-user": "user-a"})

    assert theirs.status_code == 404
    assert mine.status_code == 200


def test_an_unknown_session_is_not_found(api: TestClient) -> None:
    assert api.get("/meal-plan/sessions/does-not-exist").status_code == 404


def test_polling_returns_only_the_progress_lines_after_the_cursor(
    api: TestClient, sessions: InMemorySessionStore
) -> None:
    """A run in progress: the app has read two lines and asks for the rest."""

    def hold(session: AgentSession) -> None:
        # Stands in for a worker that has started the run and is still working.
        assert sessions.claim(session.user_sub, session.session_id, owner="attempt-1", now=utcnow())
        sessions.append_progress(
            session.user_sub, session.session_id, ["Reading", "Choosing", "Checking"], owner="attempt-1"
        )

    app.dependency_overrides[get_session_dispatcher] = lambda: hold
    created = api.post("/meal-plan/sessions", json=_body())
    app.dependency_overrides.pop(get_session_dispatcher, None)
    session_id = created.json()["session_id"]

    polled = api.get(f"/meal-plan/sessions/{session_id}", params={"after": 2}).json()
    caught_up = api.get(f"/meal-plan/sessions/{session_id}", params={"after": 3}).json()

    assert polled["status"] == "running"
    assert polled["progress"] == ["Checking"]
    assert polled["next_cursor"] == 3
    assert caught_up["progress"] == []
    assert caught_up["next_cursor"] == 3


def test_a_poll_carries_every_line_once_for_a_client_that_starts_at_zero(api: TestClient) -> None:
    created = api.post("/meal-plan/sessions", json=_body())
    session_id = created.json()["session_id"]

    first = api.get(f"/meal-plan/sessions/{session_id}", params={"after": 0}).json()
    second = api.get(f"/meal-plan/sessions/{session_id}", params={"after": first["next_cursor"]}).json()

    assert len(first["progress"]) == 3
    assert second["progress"] == []
    assert second["next_cursor"] == first["next_cursor"]


def test_polling_never_writes_to_the_session(api: TestClient, sessions: InMemorySessionStore) -> None:
    created = api.post("/meal-plan/sessions", json=_body())
    session_id = created.json()["session_id"]
    before = sessions.get("user-a", session_id)
    writes = sessions.writes

    for _ in range(4):
        api.get(f"/meal-plan/sessions/{session_id}")

    assert sessions.writes == writes
    assert sessions.get("user-a", session_id) == before


def test_a_session_is_written_with_a_ttl(api: TestClient, sessions: InMemorySessionStore) -> None:
    created = api.post("/meal-plan/sessions", json=_body())
    record = sessions.get("user-a", created.json()["session_id"])

    assert record is not None
    assert record.ttl == ttl_from(record.updated_at, SESSION_TTL_HOURS)


def test_the_post_is_rate_limited_and_the_poll_is_not(api: TestClient, test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings.model_copy(update={"rate_limit_per_hour": 1})
    try:
        client = TestClient(app)
        first = client.post("/meal-plan/sessions", json=_body())
        refused = client.post("/meal-plan/sessions", json=_body())
        polled = [client.get(f"/meal-plan/sessions/{first.json()['session_id']}").status_code for _ in range(3)]
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 202
    assert refused.status_code == 429
    assert polled == [200, 200, 200]


def test_a_request_whose_stored_session_would_not_fit_is_refused_at_create(api: TestClient) -> None:
    """S2: a body inside the schema can still be too big for one item, and the app must hear about it."""
    absurd = _body(
        recipe_history=[
            {
                "recipe_id": 1,
                "title": secrets.token_hex(400_000),  # ~800 KB of incompressible text
                "last_cooked_at": None,
                "food_groups": [],
            }
        ]
    )

    response = api.post("/meal-plan/sessions", json=absurd)

    assert response.status_code == 422
    assert "too large" in response.json()["detail"]


def test_a_large_but_realistic_history_is_planned(api: TestClient, sessions: InMemorySessionStore) -> None:
    """The review's case (2,500 saved recipes) is stored gzipped, so it plans like any other request."""
    view = _plan_to_completion(
        api,
        _body(
            recipe_history=[
                {
                    "recipe_id": index,
                    "title": (f"Slow-cooked beef ragu with tagliatelle, a Sunday sauce for the family {index}"),
                    "last_cooked_at": None,
                    "food_groups": ["protein", "veg"],
                }
                for index in range(2500)
            ]
        ),
    )

    assert view["status"] == "done"
    assert len(view["result"]["suggestions"]) == MEALS


def test_a_saved_mode_request_is_refused_by_the_session_route(api: TestClient) -> None:
    response = api.post("/meal-plan/sessions", json=_body(source="saved"))

    assert response.status_code == 422
    assert "corpus" in response.text


def test_the_session_request_takes_the_same_inputs_as_the_synchronous_route(api: TestClient) -> None:
    # V8 bounds the history at the twelve-week window plus the cooks that carry a thumbs down.
    too_much_history = [
        {"recipe_id": f"rec_{n}", "title": f"Meal {n}", "cooked_at": _iso(1)}
        for n in range(MAX_COOKED_HISTORY_ITEMS + 1)
    ]

    response = api.post("/meal-plan/sessions", json=_body(cooked_history=too_much_history))

    assert response.status_code == 422


def test_a_delivery_that_cannot_be_queued_fails_the_session_and_says_so(
    api: TestClient, sessions: InMemorySessionStore
) -> None:
    handed_over: list[AgentSession] = []

    def refuse(session: AgentSession) -> None:
        handed_over.append(session)
        raise RuntimeError("the queue is not there")

    app.dependency_overrides[get_session_dispatcher] = lambda: refuse
    created = api.post("/meal-plan/sessions", json=_body())
    app.dependency_overrides.pop(get_session_dispatcher, None)

    assert created.status_code == 503
    record = sessions.get("user-a", handed_over[0].session_id)
    assert record is not None
    assert record.status is SessionStatus.FAILED
    assert record.error is not None
    assert record.error.code is SessionErrorCode.WORKER_FAILED


def test_a_duplicate_delivery_does_not_run_the_plan_twice(api: TestClient, router: CandidatesRouter, sessions) -> None:
    created = api.post("/meal-plan/sessions", json=_body())
    record = sessions.get("user-a", created.json()["session_id"])
    assert record is not None
    session = AgentSession(session_id=record.session_id, user_sub=record.user_sub, request=record.request)
    deps = AgentDeps(sessions=sessions, checkpointer=in_memory_checkpointer(), llm_router=router)
    claims = sessions.writes

    assert start(session, deps) is False  # already finished by the inline runner
    assert sessions.writes == claims
    assert router.calls == 1


def _iso(days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


class _Throttled(Exception):
    def __init__(self, retry_after: str | None) -> None:
        super().__init__("429 Too Many Requests")
        self.status_code = 429
        self.response = type(
            "Response", (), {"status_code": 429, "headers": {"retry-after": retry_after} if retry_after else {}}
        )()


def _throttled(*, retry_after: str | None) -> Exception:
    return _Throttled(retry_after)
