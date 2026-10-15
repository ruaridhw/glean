from __future__ import annotations

import json
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


def _prepare(bucket: object, backup_id: str, note: str | None = None) -> None:
    body = json.dumps({"note": note} if note else {}).encode()
    bucket.put_object(Bucket=BUCKET, Key=f"{backup_id}PREPARED", Body=body)  # type: ignore[attr-defined]


def test_an_agent_prepared_backup_is_listed_first_and_labelled_even_when_older(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    prepared = _store_for_someone_else(bucket, "test-user-sub", _database(tmp_path)).removesuffix("glean.db")
    _prepare(bucket, prepared, note="ml to presence conversion")
    newer = _export(client, auth_headers, _database(tmp_path))

    backups = client.get("/dev/backups", headers=auth_headers).json()["backups"]

    assert [b["id"] for b in backups] == [prepared, newer]
    assert [b["prepared"] for b in backups] == [True, False]
    assert backups[0]["label"] == "ml to presence conversion"
    assert backups[1]["label"] is None


def test_a_prepared_backup_without_a_note_is_still_marked_prepared(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    prepared = _store_for_someone_else(bucket, "test-user-sub", _database(tmp_path)).removesuffix("glean.db")
    _prepare(bucket, prepared)

    backup = client.get("/dev/backups", headers=auth_headers).json()["backups"][0]

    assert backup["prepared"] is True
    assert backup["label"] is None


def test_a_backup_that_is_not_a_sqlite_file_is_listed_with_an_unknown_schema_version(
    client: TestClient, auth_headers: dict, bucket: object
) -> None:
    _export(client, auth_headers, b"not a database")

    backup = client.get("/dev/backups", headers=auth_headers).json()["backups"][0]

    assert backup["schema_version"] is None


def test_an_export_prefix_without_a_database_is_not_a_backup(
    client: TestClient, auth_headers: dict, bucket: object
) -> None:
    bucket.put_object(Bucket=BUCKET, Key="db-exports/test-user-sub/20260101T000000000000Z/app.log", Body=b"log")  # type: ignore[attr-defined]

    assert client.get("/dev/backups", headers=auth_headers).json() == {"backups": []}


def test_backups_beyond_the_first_page_of_s3_results_are_still_listed(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    # S3 lists at most 1000 keys per call, in key order: pad the user's prefix so the newest backup and a
    # prepared one fall on the second page.
    for n in range(1001):
        bucket.put_object(  # type: ignore[attr-defined]
            Bucket=BUCKET, Key=f"db-exports/test-user-sub/2025{n:04d}T000000000000Z/app.log", Body=b"x"
        )
    prepared = _store_for_someone_else(bucket, "test-user-sub", _database(tmp_path)).removesuffix("glean.db")
    _prepare(bucket, prepared)
    newest = _export(client, auth_headers, _database(tmp_path))

    backups = client.get("/dev/backups", headers=auth_headers).json()["backups"]

    assert [b["id"] for b in backups] == [prepared, newest]


def test_an_empty_backup_object_does_not_break_the_listing(
    client: TestClient, auth_headers: dict, bucket: object, tmp_path: Path
) -> None:
    good = _export(client, auth_headers, _database(tmp_path))
    empty = "db-exports/test-user-sub/20990101T000000000000Z/"
    bucket.put_object(Bucket=BUCKET, Key=f"{empty}glean.db", Body=b"")  # type: ignore[attr-defined]

    response = client.get("/dev/backups", headers=auth_headers)

    assert response.status_code == 200
    by_id = {b["id"]: b for b in response.json()["backups"]}
    assert by_id[good]["schema_version"] == 2
    assert by_id[empty]["schema_version"] is None
    assert by_id[empty]["size"] == 0
