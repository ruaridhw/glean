"""CORS exists for the local web dev loop only; the deployed Lambda sends none."""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

import glean.main as glean_main

PREFLIGHT = {
    "Origin": "http://127.0.0.1:8090",
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,content-type",
}


@pytest.fixture
def reloaded_main(monkeypatch: pytest.MonkeyPatch):
    """Re-import `glean.main` under the patched environment, then restore the original module."""

    def _reload(**env: str):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(glean_main)

    yield _reload
    monkeypatch.undo()
    importlib.reload(glean_main)


def test_local_server_answers_a_browser_preflight(reloaded_main) -> None:
    module = reloaded_main()
    assert "AWS_LAMBDA_FUNCTION_NAME" not in os.environ
    response = TestClient(module.app).options("/receipts/describe", headers=PREFLIGHT)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8090"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_lambda_sends_no_cors_headers(reloaded_main) -> None:
    module = reloaded_main(AWS_LAMBDA_FUNCTION_NAME="glean-api")
    response = TestClient(module.app).options("/receipts/describe", headers=PREFLIGHT)
    assert "access-control-allow-origin" not in response.headers
