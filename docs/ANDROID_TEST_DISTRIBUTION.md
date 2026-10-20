# Android test distribution

**Status: in use.** The [one-time setup](#one-time-setup) is done, and builds
run from `main` and install in place on the owner's Pixel. This replaced the originally planned
Fastlane lane run from the Mac. It copies the
model in [`ruaridhw/routingapp`'s `docs/ANDROID_TEST_DISTRIBUTION.md`](https://github.com/ruaridhw/routingapp/blob/main/docs/ANDROID_TEST_DISTRIBUTION.md).
iOS is out of scope for now.

## Summary

Android test builds of the Flutter app are started **by hand in Codemagic**.
Each one is release-signed and published to a **Firebase App Distribution**
tester group, and testers' phones are notified and update in place. Pushes to the
repository never start a build, so they cost no Codemagic minutes.

## Why not the Fastlane lane

| | Fastlane from the Mac (previous plan) | Codemagic → Firebase (this doc) |
|---|---|---|
| Who can release | Only someone at the Mac holding the keystore | Anyone with Codemagic access, from a browser |
| Needs a Play Console app | Yes (internal track, service-account key) | No |
| Build machine | The Mac's local toolchain, Android SDK included | Codemagic's clean builder, Flutter version pinned |
| Getting the APK onto phones | Play internal-testing opt-in | Firebase invite, then update notifications |
| Version codes | Read from every Play track | Minutes since 2024-01-01 UTC (ADR 0004) |
| Cost | Free | Free tier (500 macOS M2 minutes a month) |

The Expo app used to ship an APK as a GitHub Release on every merge to main.
Neither option kept that. The difference is that Firebase sends testers the
update without anyone forwarding a download link.

## Flow

1. Pick a branch in Codemagic and start the `android-test-distribution` workflow.
2. **Validate the release configuration.** This fails before any build work if a
   variable is missing or malformed (see [Validation](#validation)).
3. Run `flutter pub get`, `flutter analyze` and `flutter test`.
4. Write the JKS from the `keystore_credentials` group to disk with mode `0600`,
   then check its alias with `keytool`.
5. Build one universal release APK. The build uses an explicit entry point, so
   the auth-bypass `lib/main_e2e.dart` can never ship:
   ```bash
   flutter build apk --release -t lib/main.dart \
     --build-name="$APP_VERSION" \
     --build-number="$VERSION_CODE" \
     --dart-define="API_BASE_URL=$API_BASE_URL" \
     --dart-define="COGNITO_DOMAIN=$COGNITO_DOMAIN" \
     --dart-define="COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID"
   ```
   `APP_VERSION` is the `pubspec.yaml` version without its `+build` suffix.
   `VERSION_CODE` is `scripts/version_code.py`: minutes since 2024-01-01 00:00
   UTC at build time ([ADR 0004](adr/0004-timestamp-version-codes.md)), so it
   always sits above whatever the owner build installed. Codemagic's own
   `BUILD_NUMBER` stays in the release notes.
   After the build, `scripts/check_apk.py` fails the workflow if the APK is
   debuggable or carries a different versionCode.
6. **Verify the signature.** `apksigner verify --print-certs` must report
   `EXPECTED_SIGNING_CERT_SHA256`. If it doesn't, the build fails instead of
   sending testers an APK that won't install over the current one.
7. Write `release_notes.txt` with the version and build number, the short commit
   SHA, the API host and the commit subject.
8. Publish the APK to `FIREBASE_TESTER_GROUP`. Email `BUILD_NOTIFICATION_EMAIL`
   on failure only.

The workflow has no `triggering` section and runs from the `app` working
directory, on `mac_mini_m2` (the only machine the free plan covers) with Flutter pinned to the version `flutter-ci.yml`
uses (`3.44.8` at the time of writing).

## How Glean differs from routingapp

- **No compiled-in API key.** Glean's three defines (`API_BASE_URL`,
  `COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`) are public deployment identifiers.
  Users authenticate through Cognito at run time. None of them are Codemagic
  secrets, which also keeps them readable in build logs for debugging.
- **A new signing key, with no Expo compatibility.** Glean is still in
  testing, so the Flutter app gets its own key rather than reusing the
  EAS-managed one. Its signature won't match the Expo app's, so each tester
  uninstalls the Expo app once before the first Flutter install. That loses
  on-device data, which is accepted.
- **Cognito redirect is already registered.** `glean://auth/callback` and
  `glean://auth/logout` are in the user-pool client's callback lists
  (`backend/template.yaml`), and the Flutter app uses the same scheme. No
  backend change is needed.

## Validation

One script, `app/scripts/validate_release_config.py` (stdlib only), runs as
Codemagic's first step and can be run locally. It mirrors the define checks
the iOS lane makes in `app/fastlane/release_config.rb` and fails with a named
reason when:

- `API_BASE_URL` is not a public `https` URL, or has credentials, a query or a
  fragment, or points at localhost or a non-global IP;
- `COGNITO_DOMAIN` is not a bare hostname;
- `COGNITO_CLIENT_ID` is not alphanumeric;
- any variable in the groups below is missing;
- `BUILD_NUMBER` is not a positive integer;
- `CM_KEY_ALIAS` is not `glean`, or `CM_KEYSTORE_PATH` is not
  `/tmp/glean-release.jks`.

It never prints secret values. Its tests feed it environments and check which
reason it fails with.

## One-time setup

### Firebase

1. Create Firebase project `glean` and register Android app
   `com.ruaridhw.glean`. Glean needs no Firebase runtime packages for binary
   distribution. Done: project ID `glean-ruaridhw`, app ID
   `1:801300264613:android:43bd5374b41c3d9ff53f4c`.
2. In **App Distribution**, create tester group `glean-testers` and add testers.
3. Create service account `codemagic-app-distribution@glean-ruaridhw.iam.gserviceaccount.com`
   with the **Firebase App Distribution Admin** role. Store its JSON key in
   Codemagic and back it up in your password manager.

### Signing

Generate a dedicated release key once:

```bash
keytool -genkeypair -v -keystore glean-release.jks -alias glean \
  -keyalg RSA -keysize 4096 -validity 10000
```

Keep the JKS and its passwords in your password manager, with the JKS file
attached and the certificate SHA-256 recorded alongside. The key is
PKCS12, so the key password is the store password. **Never replace it**: Android
accepts an update only if it is signed by the same key. Codemagic rebuilds the
JKS on each builder from the `keystore_credentials` group, so nothing goes
under Codemagic's **Code signing identities**.

### Codemagic

The Codemagic GitHub App already reports check suites on this repository.
Add `ruaridhw/glean` as a Codemagic application if it isn't one yet, commit
`codemagic.yaml` at the repository root, and create these app-scoped variable
groups:

**`glean_config`**

| Variable | Value |
|---|---|
| `API_BASE_URL` | `https://txao8jq3c6.execute-api.eu-west-2.amazonaws.com` |
| `COGNITO_DOMAIN` | the prod Cognito hosted-UI domain |
| `COGNITO_CLIENT_ID` | the prod user-pool app-client ID |
| `EXPECTED_SIGNING_CERT_SHA256` | the release certificate's SHA-256 |
| `FIREBASE_ANDROID_APP_ID` | from the Firebase project settings |
| `FIREBASE_TESTER_GROUP` | `glean-testers` |
| `BUILD_NOTIFICATION_EMAIL` | the owner's email |

**`firebase_credentials`**: `FIREBASE_SERVICE_ACCOUNT` (the full JSON, secret).

**`keystore_credentials`**: `CM_KEYSTORE` (the JKS in base64, secret),
`CM_KEYSTORE_PASSWORD` (secret), `CM_KEY_PASSWORD` (secret), `CM_KEY_ALIAS=glean`, and
`CM_KEYSTORE_PATH=/tmp/glean-release.jks`.

### What changed, and what retires later

- The Android Fastlane lane (`app/android/fastlane/`) and its Play
  service-account requirement are gone. `app/fastlane/release_config.rb`
  stays for the iOS lane.
- `app/android/app/build.gradle.kts` signs with the `CM_*` keystore when
  `CM_KEYSTORE_PATH` is set, else with a local `key.properties`, else with the
  debug key (which the signature check refuses to distribute).

The Expo `deploy` job and its GitHub Release APKs went away with `mobile/`
when the Flutter app merged (#102).

## Owner build

The owner's phone also gets a build made on gordon, not Codemagic: the same
release build with Android's debuggable flag on, so `adb` can copy the app's
database and log file and stream the `glean` log tag. It has the same
application id and the same release key as tester builds, so it installs over
the existing app and keeps all data. Tester builds stay non-debuggable.

```bash
API_BASE_URL=... COGNITO_DOMAIN=... COGNITO_CLIENT_ID=... \
EXPECTED_SIGNING_CERT_SHA256=... \
OP_KEYSTORE_REF=op://... OP_KEYSTORE_PASSWORD_REF=op://... OP_KEY_PASSWORD_REF=op://... \
  app/scripts/owner_build.sh
```

- The key is read from 1Password into a temporary file only the owner can
  read, and deleted when the script exits. It is never written into the repo.
- The script sets `GLEAN_OWNER_BUILD=1`, which turns on `android:debuggable`
  and makes Gradle refuse to fall back to debug signing.
- It checks the certificate fingerprint and, with `scripts/check_apk.py`, that
  the APK is debuggable with the timestamp versionCode.
- **It never installs.** Install by hand, with the owner present, only after a
  verified Export diagnostics of the phone exists (it downloads, opens with
  `sqlite3`, row counts match): `adb install -r app-release.apk`. Never
  uninstall first, never use another key, never a lower versionCode.
- Prove the install-over behaviour on an emulator (tester build with data,
  then the owner build over it) before the phone.

## Export diagnostics

Settings has a developer-only **Export diagnostics** action: tap the version
label 7 times to show it (per session, on release builds too). It uploads a
consistent snapshot of the database plus the rotating log file through
`POST /dev/export-db`, which stores them under
`db-exports/<user id>/<UTC timestamp>/` in the receipts bucket. That prefix is
kept 30 days (the bucket's one-day rule covers only `receipts/`). Fetch with
the `glean` AWS profile; no adb is needed.

## Tester installation

1. Accept the Firebase App Distribution invitation on the phone.
2. Open the new-build notification and download the APK. When Android asks,
   allow installs from Firebase or the browser.
3. For later builds, install over the top. Don't uninstall first.

If Android reports an incompatible signature, stop and report the build. Don't
uninstall as a routine workaround: it erases the on-device pantry, plan and
shopping list.

## First-build acceptance check

- [x] Validation, analysis and tests passed in Codemagic.
- [x] Signature verification passed.
- [x] Firebase lists the expected version and build number.
- [x] After uninstalling the Expo app, the APK installs on a phone.
- [x] Sign in with Google, then run one AI flow (shop describe) and one corpus
      flow (Generate) against prod.
- [x] Start a second build from a harmless change and confirm it updates in
      place. Builds 3 and 8 updated over earlier builds with the user's data
      kept.
