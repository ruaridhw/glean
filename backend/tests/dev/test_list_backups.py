from __future__ import annotations

import sqlite3
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from glean.config import Settings, get_settings
from glean.main import app

if TYPE_CHECKING:
    from pathlib import Path

BUCKET = "test-s3_receipts_bucket"


def _database(tmp_path: Path, schema_version: int = 2) -> bytes:
    path = tmp_path / f"v{schema_version}-{len(list(tmp_path.iterdir()))}.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE pantry_items (id INTEGER PRIMARY KEY)")
    connection.execute(f"PRAGMA user_version = {schema_version}")
    connection.commit()
    connection.close()
    return path.read_bytes()


def _export(client: TestClient, auth_headers: dict, database: bytes) -> str:
    response = client.post(
        "/dev/export-db",
        files={
            "database": ("glean.db", BytesIO(database), "application/octet-stream"),
            "log": ("glean.log", BytesIO(b"log"), "text/plain"),
        },
        headers=auth_headers,
    )
    return response.json()["prefix"]


def test_a_user_lists_their_own_backups_newest_first_with_short_lived_download_urls(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    older = _export(client, auth_headers, _database(tmp_path, schema_version=1))
    newer = _export(client, auth_headers, _database(tmp_path, schema_version=2))

    response = client.get("/dev/backups", headers=auth_headers)

    assert response.status_code == 200
    backups = response.json()["backups"]
    assert [b["id"] for b in backups] == [newer, older]
    assert [b["schema_version"] for b in backups] == [2, 1]
    assert [b["prepared"] for b in backups] == [False, False]
    url = urlparse(backups[0]["download_url"])
    assert url.path.endswith(f"/{newer}glean.db")
    assert parse_qs(url.query)["X-Amz-Expires"] == ["300"]


def _store_for_someone_else(bucket: object, user: str, database: bytes) -> str:
    key = f"db-exports/{user}/20260101T000000000000Z/glean.db"
    bucket.put_object(Bucket=BUCKET, Key=key, Body=database)  # type: ignore[attr-defined]
    return key


def test_one_user_never_sees_another_users_backups(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    mine = _export(client, auth_headers, _database(tmp_path))
    # "test-user-sub2" shares a name prefix with the caller "test-user-sub"; "other" does not.
    _store_for_someone_else(bucket, "test-user-sub2", _database(tmp_path, schema_version=1))
    _store_for_someone_else(bucket, "other-user", _database(tmp_path, schema_version=1))

    response = client.get("/dev/backups", headers=auth_headers)

    assert [b["id"] for b in response.json()["backups"]] == [mine]
    assert "other-user" not in response.text
    assert "test-user-sub2" not in response.text


def test_client_supplied_scope_cannot_widen_the_listing_to_another_user(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    mine = _export(client, auth_headers, _database(tmp_path))
    _store_for_someone_else(bucket, "other-user", _database(tmp_path))

    for scope in ("user=other-user", "user_id=other-user", "prefix=db-exports/other-user/", "sub=other-user"):
        response = client.get(f"/dev/backups?{scope}", headers=auth_headers)
        assert [b["id"] for b in response.json()["backups"]] == [mine], scope


def test_listing_requires_a_signed_in_user(test_settings: Settings) -> None:
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        assert TestClient(app).get("/dev/backups").status_code == 401
    finally:
        app.dependency_overrides.clear()
