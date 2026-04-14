from __future__ import annotations

import os
from typing import Any


def _get_allowed_emails() -> set[str]:
    """Read allowlist from Secrets Manager (Lambda) or ALLOWED_EMAILS env var (tests)."""
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        env = os.environ.get("ENVIRONMENT", "prod")
        try:
            import boto3

            client = boto3.client("secretsmanager")
            resp = client.get_secret_value(SecretId=f"glean/{env}/allowed-emails")
            raw = resp.get("SecretString", "")
        except Exception:
            raw = ""
    else:
        raw = os.environ.get("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    allowed = _get_allowed_emails()

    email = event["request"]["userAttributes"].get("email", "").lower()

    if allowed and email not in allowed:
        raise Exception(f"Email {email} is not in the allowlist")

    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyEmail"] = True
    return event
