"""S3 fixtures shared by the /dev endpoint tests: a moto bucket, never a real one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
import pytest
from moto import mock_aws

if TYPE_CHECKING:
    from collections.abc import Iterator

    from glean.config import Settings

BUCKET = "test-s3_receipts_bucket"


@pytest.fixture
def bucket(test_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        s3 = boto3.client("s3", region_name=test_settings.aws_region)
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": test_settings.aws_region},
        )
        yield s3
