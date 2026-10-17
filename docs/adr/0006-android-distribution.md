---
status: accepted
date: 2026-10-09
---

# Android tester builds go Codemagic → Firebase App Distribution; owner builds are made on the home server

Two build pipelines exist on purpose. **Tester builds** are started by hand on Codemagic's free macOS machines, signed with the release key, and published to Firebase App Distribution (`codemagic.yaml`, `docs/ANDROID_TEST_DISTRIBUTION.md`). **Owner builds** are built on the always-on home server with a locally installed Android SDK and installed straight onto the owner's Pixel over adb, so a fix can be on the phone without a CI round-trip. The owner build installs *over* the installed app so its data survives; ADR 0004's timestamp versionCodes are what let the two pipelines coexist without a shared counter.

## Considered options

- **Fastlane from the Mac.** Rejected: it needs the Mac awake and driven; Codemagic's free tier does the macOS builds, and the home server is always on.
- **EAS Build.** Dead with the Expo app (ADR 0005).
- **Only Codemagic, no owner builds.** Rejected: the owner build exists precisely to keep the phone's data while iterating quickly.

## Consequences

- **A fresh signing key was cut for the Flutter app.** The app is in testing, so no backwards compatibility with Expo-era installs was needed.
- **Firebase stays manual on purpose.** Installing a tester build from App Distribution is two taps; no over-the-air machinery was added.
- **Codemagic's own build number** still appears in the release notes, but install order is decided by ADR 0004's timestamp, not by either pipeline's counter.
