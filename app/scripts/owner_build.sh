#!/usr/bin/env bash
# Builds the owner build on gordon: a release-speed APK with Android's debuggable flag on, the same application
# id and the same release signing key as the tester builds, so it installs over the existing app with
# `adb install -r` and keeps all data (docs/ANDROID_TEST_DISTRIBUTION.md, "Owner build").
#
# The signing key comes from 1Password at build time into a temporary file only the owner can read, and is
# deleted when this script exits, however it exits. This script builds and verifies; it NEVER installs.
# Required environment: API_BASE_URL COGNITO_DOMAIN COGNITO_CLIENT_ID EXPECTED_SIGNING_CERT_SHA256
#   OP_KEYSTORE_REF OP_KEYSTORE_PASSWORD_REF OP_KEY_PASSWORD_REF (1Password `op://` references)
# Optional: GLEAN_KEY_ALIAS (default glean), ANDROID_SDK_ROOT (default ~/Android/Sdk).
set -euo pipefail
umask 077

fail() { echo "owner_build: $*" >&2; exit 1; }

for name in API_BASE_URL COGNITO_DOMAIN COGNITO_CLIENT_ID EXPECTED_SIGNING_CERT_SHA256 \
  OP_KEYSTORE_REF OP_KEYSTORE_PASSWORD_REF OP_KEY_PASSWORD_REF; do
  [ -n "${!name:-}" ] || fail "$name must be set"
done

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${GLEAN_APP_DIR:-$(dirname "$SCRIPTS_DIR")}"
SDK="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
cd "$APP_DIR"

KEYSTORE="$(mktemp "${TMPDIR:-/tmp}/glean-owner-XXXXXX.jks")"
trap 'rm -f "$KEYSTORE"' EXIT

op read --force --out-file "$KEYSTORE" "$OP_KEYSTORE_REF" >/dev/null
test -s "$KEYSTORE" || fail "the keystore from 1Password is empty"

# Same variable names the Gradle release signing config reads on Codemagic.
export CM_KEYSTORE_PATH="$KEYSTORE"
CM_KEYSTORE_PASSWORD="$(op read "$OP_KEYSTORE_PASSWORD_REF")"
CM_KEY_PASSWORD="$(op read "$OP_KEY_PASSWORD_REF")"
export CM_KEYSTORE_PASSWORD CM_KEY_PASSWORD
export CM_KEY_ALIAS="${GLEAN_KEY_ALIAS:-glean}"
# Turns on android:debuggable for the release build type, and makes Gradle refuse to fall back to debug signing.
export GLEAN_OWNER_BUILD=1

APP_VERSION="$(awk '/^version:/ {print $2}' pubspec.yaml | cut -d+ -f1)"
VERSION_CODE="$(python3 "$SCRIPTS_DIR/version_code.py")"

APK="build/app/outputs/flutter-apk/app-release.apk"
# An APK from an earlier tester or owner build must never be mistaken for this one.
rm -f "$APK"

flutter build apk --release -t lib/main.dart \
  --build-name="$APP_VERSION" \
  --build-number="$VERSION_CODE" \
  --dart-define="API_BASE_URL=$API_BASE_URL" \
  --dart-define="COGNITO_DOMAIN=$COGNITO_DOMAIN" \
  --dart-define="COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID"

[ -f "$APK" ] || fail "flutter build did not produce $APK"
APKSIGNER="$(find "$SDK/build-tools" -type f -name apksigner | sort -V | tail -1)"
test -x "$APKSIGNER" || fail "apksigner not found under $SDK/build-tools"

normalise() { tr '[:lower:]' '[:upper:]' | tr -d ':[:space:]'; }
ACTUAL="$("$APKSIGNER" verify --verbose --print-certs "$APK" | sed -n 's/^Signer #1 certificate SHA-256 digest: //p' | head -1 | normalise)"
EXPECTED="$(printf '%s' "$EXPECTED_SIGNING_CERT_SHA256" | normalise)"
[ -n "$ACTUAL" ] && [ "$ACTUAL" = "$EXPECTED" ] || fail "release certificate fingerprint mismatch: built with the wrong key"

python3 "$SCRIPTS_DIR/check_apk.py" "$APK" --expect owner --version-code "$VERSION_CODE"

echo "Owner build ready: $APP_DIR/$APK (versionName $APP_VERSION, versionCode $VERSION_CODE)"
echo "Not installed. With the owner present and a verified Export diagnostics in hand, install over the app with:"
echo "  adb -s <device> install -r $APP_DIR/$APK"
