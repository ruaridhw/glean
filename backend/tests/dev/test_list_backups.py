from __future__ import annotations

import sqlite3
from io import BytesIO
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

if TYPE_CHECKING:
    from pathlib import Path

    from fastapi.testclient import TestClient

BUCKET = "test-s3_receipts_bucket"
# `bucket` and its helpers live in test_export_db; pytest needs the fixture imported by name.
from tests.dev.test_export_db import bucket  # noqa: E402, F401, I001


def _database(tmp_path: Path, schema_version: int = 2) -> bytes:
    path = tmp_path / f"v{schema_version}.sqlite"
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
