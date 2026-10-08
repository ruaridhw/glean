"""Fail a Codemagic Android release build before any work if its config is wrong.

Run as the first step of `android-test-distribution` (codemagic.yaml); see
docs/ANDROID_TEST_DISTRIBUTION.md. Stdlib only. Prints variable names and
reasons, never values, since several of the variables are secrets.
"""

import ipaddress
import os
import re
import sys
from collections.abc import Mapping
from urllib.parse import urlsplit

REQUIRED = (
    "API_BASE_URL",
    "COGNITO_DOMAIN",
    "COGNITO_CLIENT_ID",
    "EXPECTED_SIGNING_CERT_SHA256",
    "FIREBASE_ANDROID_APP_ID",
    "FIREBASE_TESTER_GROUP",
    "BUILD_NOTIFICATION_EMAIL",
    "FIREBASE_SERVICE_ACCOUNT",
    "CM_KEYSTORE",
    "CM_KEYSTORE_PASSWORD",
    "CM_KEY_PASSWORD",
    "CM_KEY_ALIAS",
    "CM_KEYSTORE_PATH",
    "BUILD_NUMBER",
)
KEY_ALIAS = "glean"
KEYSTORE_PATH = "/tmp/glean-release.jks"


def _api_base_url_problem(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        port_ok = parsed.port is None or parsed.port > 0
    except ValueError:
        return "API_BASE_URL is not a valid URL"
    host = (parsed.hostname or "").rstrip(".").lower()
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if (
        parsed.scheme != "https"
        or not host
        or not port_ok
        or host == "localhost"
        or host.endswith(".localhost")
        or (ip is not None and not ip.is_global)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return (
            "API_BASE_URL must be a public https URL without credentials, "
            "query or fragment"
        )
    return None


def problems(env: Mapping[str, str]) -> list[str]:
    """Every reason `env` can't produce a distributable build; empty when it can."""
    values = {name: env.get(name, "").strip() for name in REQUIRED}
    found = [f"{name} is missing" for name, value in values.items() if not value]

    if values["API_BASE_URL"] and (issue := _api_base_url_problem(values["API_BASE_URL"])):
        found.append(issue)
    if values["COGNITO_DOMAIN"] and not re.fullmatch(
        r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+", values["COGNITO_DOMAIN"]
    ):
        found.append("COGNITO_DOMAIN must be a bare hostname, without scheme or path")
    if values["COGNITO_CLIENT_ID"] and not re.fullmatch(
        r"[A-Za-z0-9]+", values["COGNITO_CLIENT_ID"]
    ):
        found.append("COGNITO_CLIENT_ID must be a Cognito app-client ID (letters and digits)")
    if values["BUILD_NUMBER"] and not re.fullmatch(r"[1-9][0-9]*", values["BUILD_NUMBER"]):
        found.append("BUILD_NUMBER must be a positive integer")
    if values["CM_KEY_ALIAS"] and values["CM_KEY_ALIAS"] != KEY_ALIAS:
        found.append(f"CM_KEY_ALIAS must be {KEY_ALIAS}")
    if values["CM_KEYSTORE_PATH"] and values["CM_KEYSTORE_PATH"] != KEYSTORE_PATH:
        found.append(f"CM_KEYSTORE_PATH must be {KEYSTORE_PATH}")
    return found


def main() -> int:
    found = problems(os.environ)
    for problem in found:
        print(f"release config: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
