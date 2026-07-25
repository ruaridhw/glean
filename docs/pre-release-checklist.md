# Manual Pre-Release Checklist

Run this by hand on real devices or simulators before every TestFlight or
Play upload. It covers checks that are deliberately not automated.

## 1. Airplane-mode and offline error states

Turn on airplane mode (or disable Wi-Fi and cellular), exercise every flow
below, and confirm the stated error appears instead of a hang, frozen screen,
or silent failure. Restore connectivity and confirm retry succeeds.

- [ ] Preserve the intent of the retired Maestro flow’s global offline-banner
      check: while offline, confirm network-backed actions surface their
      contextual errors rather than a global banner; after reconnecting,
      confirm no stale offline/error state remains. The Flutter port
      deliberately has no always-on connectivity monitor or global “You’re
      offline” banner, so successful retries are its recovery signal.
- [ ] Meals → Search shows “Search failed. Check your connection and try
      again.” Resubmitting after reconnecting returns results.
- [ ] Intake → Scan receipt shows “Could not process the receipt. Try again
      or add items manually.” Both Back and Try again work; retry succeeds
      after reconnecting.
- [ ] Intake → Describe (Pantry) shows its “Could not understand that”
      message without hanging or crashing.
- [ ] Intake → Describe (Shop) shows its “Could not turn that into a list”
      message without hanging or crashing.
- [ ] Plan → Generate shows “Could not generate meal plan.” The Generate
      button re-enables, and retry fills the week after reconnecting.
- [ ] Meals → Import by URL shows “Could not import this recipe. Check the
      link and try again.” Retry succeeds after reconnecting.
- [ ] Sign-in reports a failed sign-in, leaves the screen usable, and
      succeeds after reconnecting.
- [ ] Manual entry and Review confirmation still work while offline; both
      are local database writes and must not depend on connectivity.

## 2. Integration tests on both platforms

Run the suite on a Mac that has the signing toolchain and credentials. The
exact commands and required `--dart-define` values are in
[`app/README.md`](../app/README.md#running-it-locally).

- [ ] iOS Simulator: `flutter test integration_test/app_test.dart -d <UDID>
      --dart-define=...`
- [ ] Android emulator: run the same suite with `-d emulator-5554`
- [ ] Confirm all five tabs are visible and navigable, camera-permission
      handling works on Scan, and manual-entry add succeeds.

If either platform fails, stop before signing or uploading.

## 3. Signing and build numbers

### iOS (`app/ios/fastlane/Fastfile`, lane `beta`)

- [ ] Automatic signing is enabled for Runner and a valid Apple Developer
      team is selected.
- [ ] `ASC_KEY_ID`, `ASC_ISSUER_ID`, and `ASC_KEY_CONTENT` are set.
- [ ] For the first pipeline upload, compare the next build number against
      every existing TestFlight build, including builds uploaded manually.

### Android (`app/android/fastlane/Fastfile`, lane `internal`)

- [ ] `app/android/key.properties` points to the real upload keystore, not a
      debug keystore.
- [ ] `PLAY_STORE_JSON_KEY` names a service-account key authorized for this
      app.
- [ ] For the first pipeline upload, compare the next version code against
      every existing Play Console upload.

### Both platforms

- [ ] `app/pubspec.yaml`’s marketing version is the version intended for
      release; the lanes increment build numbers, not the marketing version.
- [ ] The Terms of Service and Privacy Policy URLs configured in
      `lib/features/settings/widgets/legal_links_section.dart` are hosted and
      reachable.
- [ ] iOS usage-description strings, including
      `NSCameraUsageDescription`, are user-facing and accurate.
- [ ] Complete a real Cognito sign-in on a physical device for each platform.
      Integration tests use `main_e2e.dart` and do not verify the real hosted
      UI redirect through the operating system.
