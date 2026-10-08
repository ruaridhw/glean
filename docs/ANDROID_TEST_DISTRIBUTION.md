# Android test distribution

**Status: proposed, not yet built.** This replaces the Android half of
`FLUTTER_MIGRATION.md` §8 (the Fastlane lane run from the Mac). It copies the
model in [`ruaridhw/routingapp`'s `docs/ANDROID_TEST_DISTRIBUTION.md`](https://github.com/ruaridhw/routingapp/blob/main/docs/ANDROID_TEST_DISTRIBUTION.md).
iOS is out of scope for now.

## Summary

Android test builds of the Flutter app are started **by hand in Codemagic**.
Each one is release-signed and published to a **Firebase App Distribution**
tester group, and testers' phones are notified and update in place. Pushes to the
repository never start a build, so they cost no Codemagic minutes.

## Why not the Fastlane lane

| | Fastlane from the Mac (current §8) | Codemagic → Firebase (this doc) |
|---|---|---|
| Who can release | Only someone at the Mac holding the keystore | Anyone with Codemagic access, from a browser |
| Needs a Play Console app | Yes (internal track, service-account key) | No |
| Build machine | The Mac's local toolchain, Android SDK included | Codemagic's clean builder, Flutter version pinned |
| Getting the APK onto phones | Play internal-testing opt-in | Firebase invite, then update notifications |
| Version codes | Read from every Play track | Codemagic `BUILD_NUMBER` plus a fixed base |
| Cost | Free | Free tier (500 Linux minutes a month) |

Today the Expo app ships an APK as a GitHub Release on every merge to main.
Neither option keeps that. The difference is that Firebase sends testers the
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
     --build-number="$((ANDROID_VERSION_CODE_BASE + BUILD_NUMBER))" \
     --dart-define="API_BASE_URL=$API_BASE_URL" \
     --dart-define="COGNITO_DOMAIN=$COGNITO_DOMAIN" \
     --dart-define="COGNITO_CLIENT_ID=$COGNITO_CLIENT_ID"
   ```
   `APP_VERSION` is the `pubspec.yaml` version without its `+build` suffix.
6. **Verify the signature.** `apksigner verify --print-certs` must report
   `EXPECTED_SIGNING_CERT_SHA256`. If it doesn't, the build fails instead of
   sending testers an APK that won't install over the current one.
7. Write `release_notes.txt` with the version and build number, the short commit
   SHA, the API host and the commit subject.
8. Publish the APK to `FIREBASE_TESTER_GROUP`. Email `BUILD_NOTIFICATION_EMAIL`
   on failure only.

The workflow has no `triggering` section and runs from the `app` working
directory, on `linux_x2` with Flutter pinned to the version `flutter-ci.yml`
uses (`3.44.8` at the time of writing).

## How Glean differs from routingapp

- **No compiled-in API key.** Glean's three defines (`API_BASE_URL`,
  `COGNITO_DOMAIN`, `COGNITO_CLIENT_ID`) are public deployment identifiers.
  Users authenticate through Cognito at run time. None of them are Codemagic
  secrets, which also keeps them readable in build logs for debugging.
- **The signing key has history.** The live Expo app (`com.ruaridhw.glean`) is
  signed by an EAS-managed key. See [Decision 1](#decision-1-which-signing-key).
- **Version codes must start above Expo's.** EAS increments the Expo app's
  version code remotely. For the Flutter APK to install as an update, its code
  must be higher, hence `ANDROID_VERSION_CODE_BASE`.
- **Cognito redirect is already registered.** `glean://auth/callback` and
  `glean://auth/logout` are in the user-pool client's callback lists
  (`backend/template.yaml`), and the Flutter app uses the same scheme. No
  backend change is needed.

## Validation

One script, `app/tool/validate_release_config.py` (stdlib only), runs as
Codemagic's first step and can be run locally. It replaces the checks in
`app/fastlane/release_config.rb` and fails with a named reason when:

- `API_BASE_URL` is not a public `https` URL, or has credentials, a query or a
  fragment, or points at localhost or a non-global IP;
- `COGNITO_DOMAIN` is not a bare hostname;
- `COGNITO_CLIENT_ID` is not alphanumeric;
- any variable in the groups below is missing;
- `ANDROID_VERSION_CODE_BASE` or `BUILD_NUMBER` is not a positive integer;
- `CM_KEYSTORE_PATH` is not `/tmp/glean-release.jks`.

It never prints secret values. Its tests feed it environments and check which
reason it fails with.

## One-time setup

### Firebase

1. Create Firebase project `glean` and register Android app
   `com.ruaridhw.glean`. Glean needs no Firebase runtime packages for binary
   distribution.
2. In **App Distribution**, create tester group `glean-testers` and add testers.
3. Create service account `codemagic-app-distribution@<project>.iam.gserviceaccount.com`
   with the **Firebase App Distribution Admin** role. Store its JSON key in
   Codemagic and back it up at
   `op://Homelab/Glean Firebase App Distribution/credential`.

### Signing

Keep the release JKS and its passwords in 1Password at
`op://Homelab/Glean Android Release Signing`. **Never replace it**: Android
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
| `ANDROID_VERSION_CODE_BASE` | above the last Expo version code (see Decision 1) |
| `EXPECTED_SIGNING_CERT_SHA256` | the release certificate's SHA-256 |
| `FIREBASE_ANDROID_APP_ID` | from the Firebase project settings |
| `FIREBASE_TESTER_GROUP` | `glean-testers` |
| `BUILD_NOTIFICATION_EMAIL` | the owner's email |

**`firebase_credentials`**: `FIREBASE_SERVICE_ACCOUNT` (the full JSON, secret).

**`keystore_credentials`**: `CM_KEYSTORE` (the JKS in base64, secret),
`CM_KEYSTORE_PASSWORD` (secret), `CM_KEY_PASSWORD` (secret), `CM_KEY_ALIAS`, and
`CM_KEYSTORE_PATH=/tmp/glean-release.jks`.

## Decisions

### Decision 1: which signing key

- **A. Reuse the EAS key (recommended).** Download it once with
  `eas credentials --platform android` and store it in 1Password.
  - Phones running Expo v0.1.x then take the first Flutter APK as an ordinary
    update, with no uninstall and no "incompatible signature" error.
  - Set `ANDROID_VERSION_CODE_BASE` above the current EAS version code
    (`eas build:version:get --platform android`).
  - Local data doesn't carry over either way. Flutter's drift database is a new
    file, and §1 already accepts data loss at cutover.
- **B. Generate a new key.** Simpler on paper, but every tester has to
  uninstall the Expo app once before the first Flutter install.
  `ANDROID_VERSION_CODE_BASE` can then be `0`.

### Decision 2: what retires, and when

When `codemagic.yaml` lands:

- delete the Android Fastlane lane, `app/android/fastlane/`, and the Play
  service-account requirement;
- move the define checks from `app/fastlane/release_config.rb` into the
  validator, keeping the Ruby file only if the iOS lane still needs it;
- update `FLUTTER_MIGRATION.md` §8 to point here.

At cutover (merging the Flutter port), the Expo `deploy` job and its GitHub
Release APKs go away with `mobile/`.

## Tester installation

1. Accept the Firebase App Distribution invitation on the phone.
2. Open the new-build notification and download the APK. When Android asks,
   allow installs from Firebase or the browser.
3. For later builds, install over the top. Don't uninstall first.

If Android reports an incompatible signature, stop and report the build. Don't
uninstall as a routine workaround: it erases the on-device pantry, plan and
shopping list.

## First-build acceptance check

- [ ] Validation, analysis and tests passed in Codemagic.
- [ ] Signature verification passed.
- [ ] Firebase lists the expected version and build number.
- [ ] With Decision 1A: the APK installs over Expo v0.1.x as an update.
- [ ] Sign in with Google, then run one AI flow (shop describe) and one corpus
      flow (Generate) against prod.
- [ ] Start a second build from a harmless change and confirm it updates in
      place.
