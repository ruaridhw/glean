from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
from pydantic import SecretStr

from glean.decisions import DecisionClient
from glean.dependencies import get_decision_client
from glean.main import app
from glean.recipe_api.blob_store import FilesystemBlobStore, get_shopping_parse_store

if TYPE_CHECKING:
    from pathlib import Path


def _ambiguous_decision(request: httpx.Request) -> httpx.Response:
    names = json.loads(request.content)["questions"]
    scores = {"names_a_dish": 0.5, "lists_several_items": 0.1}
    return httpx.Response(
        200,
        json={
            "id": "gen-dec-1",
            "model": "typesafe/jev-1.14-20261014",
            "provider": "TypeSafe",
            "answers": {name: {"type": "noul", "noul": scores[name]} for name in names},
            "usage": {"input_tokens": 10, "output_tokens": 1, "cost": 0.0},
        },
    )


@pytest.fixture
def decision_client() -> DecisionClient:
    return DecisionClient(api_key=SecretStr("test"), transport=httpx.MockTransport(_ambiguous_decision))


@pytest.fixture
def parse_cache(tmp_path: Path) -> FilesystemBlobStore:
    return FilesystemBlobStore(tmp_path)


@pytest.fixture(autouse=True)
def _local_decisions_and_cache(decision_client: DecisionClient, parse_cache: FilesystemBlobStore) -> None:
    """HTTP tests get a canned decision endpoint and a throwaway cache, never the network or `.cache/`."""
    app.dependency_overrides[get_decision_client] = lambda: decision_client
    app.dependency_overrides[get_shopping_parse_store] = lambda: parse_cache
