from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


BUCKET = "test-s3_receipts_bucket"


def _stored(s3: object) -> dict[str, bytes]:
    listing = s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])  # type: ignore[attr-defined]
    return {
        item["Key"]: s3.get_object(Bucket=BUCKET, Key=item["Key"])["Body"].read()  # type: ignore[attr-defined]
        for item in listing
    }


def _export(
    client: TestClient, auth_headers: dict, database: bytes = b"SQLite format 3\x00", log: bytes = b"log line\n"
):
    return client.post(
        "/dev/export-db",
        files={
            "database": ("glean.db", BytesIO(database), "application/octet-stream"),
            "log": ("glean.log", BytesIO(log), "text/plain"),
        },
        headers=auth_headers,
    )


def test_export_stores_database_and_log_under_the_users_timestamped_prefix(
    client: TestClient, auth_headers: dict, bucket: object
) -> None:
    response = _export(client, auth_headers, database=b"db-bytes", log=b"log-bytes")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "uploaded"
    prefix = body["prefix"]
    assert prefix.startswith("db-exports/test-user-sub/")
    assert prefix.endswith("Z/")
    assert _stored(bucket) == {
        f"{prefix}glean.db": b"db-bytes",
        f"{prefix}app.log": b"log-bytes",
    }


def test_two_exports_in_a_row_land_under_separate_prefixes(
    client: TestClient, auth_headers: dict, bucket: object
) -> None:
    first = _export(client, auth_headers, database=b"first").json()["prefix"]
    second = _export(client, auth_headers, database=b"second").json()["prefix"]

    assert first != second
    stored = _stored(bucket)
    assert stored[f"{first}glean.db"] == b"first"
    assert stored[f"{second}glean.db"] == b"second"


def test_upload_filenames_cannot_steer_the_stored_key(client: TestClient, auth_headers: dict, bucket: object) -> None:
    response = client.post(
        "/dev/export-db",
        files={
            "database": ("../../other-user/glean.db", BytesIO(b"db"), "application/octet-stream"),
            "log": ("../x.log", BytesIO(b"log"), "text/plain"),
        },
        headers=auth_headers,
    )

    prefix = response.json()["prefix"]
    assert sorted(_stored(bucket)) == [f"{prefix}app.log", f"{prefix}glean.db"]


def test_an_export_without_a_log_is_rejected_and_stores_nothing(
    client: TestClient, auth_headers: dict, bucket: object
) -> None:
    response = client.post(
        "/dev/export-db",
        files={"database": ("glean.db", BytesIO(b"db"), "application/octet-stream")},
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert _stored(bucket) == {}
