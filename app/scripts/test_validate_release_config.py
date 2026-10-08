"""Behaviour of the Codemagic release-config gate (docs/ANDROID_TEST_DISTRIBUTION.md)."""

import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from validate_release_config import problems  # noqa: E402

SCRIPT = Path(__file__).parent / "validate_release_config.py"

VALID = {
    "API_BASE_URL": "https://txao8jq3c6.execute-api.eu-west-2.amazonaws.com",
    "COGNITO_DOMAIN": "glean-auth-040396448697.auth.eu-west-2.amazoncognito.com",
    "COGNITO_CLIENT_ID": "abc123def456",
    "EXPECTED_SIGNING_CERT_SHA256": "AB:CD:EF",
    "FIREBASE_ANDROID_APP_ID": "1:123:android:abc",
    "FIREBASE_TESTER_GROUP": "glean-testers",
    "BUILD_NOTIFICATION_EMAIL": "owner@example.com",
    "FIREBASE_SERVICE_ACCOUNT": '{"type": "service_account"}',
    "CM_KEYSTORE": "c2VjcmV0LWtleXN0b3Jl",
    "CM_KEYSTORE_PASSWORD": "store-secret-value",
    "CM_KEY_PASSWORD": "key-secret-value",
    "CM_KEY_ALIAS": "glean",
    "CM_KEYSTORE_PATH": "/tmp/glean-release.jks",
    "BUILD_NUMBER": "7",
}


def with_(**overrides: str | None) -> dict[str, str]:
    env = {**VALID, **overrides}
    return {k: v for k, v in env.items() if v is not None}


class ReleaseConfigTest(unittest.TestCase):
    def assertRejected(self, env: dict[str, str], fragment: str) -> None:
        found = problems(env)
        self.assertTrue(
            any(fragment in p for p in found),
            f"expected a problem mentioning {fragment!r}, got {found}",
        )

    def test_complete_production_config_is_accepted(self) -> None:
        self.assertEqual(problems(VALID), [])

    def test_every_missing_or_blank_variable_is_named(self) -> None:
        for name in VALID:
            with self.subTest(missing=name):
                self.assertRejected(with_(**{name: None}), name)
            with self.subTest(blank=name):
                self.assertRejected(with_(**{name: "  "}), name)

    def test_api_base_url_must_be_public_https_without_extras(self) -> None:
        for url in [
            "http://txao8jq3c6.execute-api.eu-west-2.amazonaws.com",
            "https://localhost:8000",
            "https://api.localhost",
            "https://127.0.0.1",
            "https://10.0.2.2:8000",
            "https://user:pw@example.com",
            "https://example.com/?stage=dev",
            "https://example.com/#x",
            "not a url",
        ]:
            with self.subTest(url=url):
                self.assertRejected(with_(API_BASE_URL=url), "API_BASE_URL")

    def test_cognito_values_must_be_identifiers_not_urls(self) -> None:
        self.assertRejected(
            with_(COGNITO_DOMAIN="https://glean.auth.eu-west-2.amazoncognito.com"),
            "COGNITO_DOMAIN",
        )
        self.assertRejected(with_(COGNITO_DOMAIN="glean/oauth2"), "COGNITO_DOMAIN")
        self.assertRejected(with_(COGNITO_CLIENT_ID="abc-123"), "COGNITO_CLIENT_ID")

    def test_build_number_must_be_a_positive_integer(self) -> None:
        for value in ["0", "-1", "1.5", "abc", "01"]:
            with self.subTest(build_number=value):
                self.assertRejected(with_(BUILD_NUMBER=value), "BUILD_NUMBER")

    def test_keystore_location_and_alias_are_pinned(self) -> None:
        self.assertRejected(with_(CM_KEY_ALIAS="upload"), "CM_KEY_ALIAS")
        self.assertRejected(with_(CM_KEYSTORE_PATH="/tmp/other.jks"), "CM_KEYSTORE_PATH")

    def test_cli_fails_without_echoing_secret_values(self) -> None:
        env = with_(API_BASE_URL="http://insecure.example.com", CM_KEY_ALIAS="upload")
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env={**env, "PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("API_BASE_URL", output)
        for secret in ("CM_KEYSTORE", "CM_KEYSTORE_PASSWORD", "CM_KEY_PASSWORD"):
            self.assertNotIn(VALID[secret], output)

    def test_cli_succeeds_on_valid_config(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env={**VALID, "PATH": os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
