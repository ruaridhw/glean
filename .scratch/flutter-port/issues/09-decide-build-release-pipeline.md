Type: grilling
Status: resolved
Blocked by: 05

## Question

Given the research in ticket 05 (`.scratch/flutter-port/research/build-release-macos-ci.md`), decide the iOS/Android signing & release pipeline: manual certs vs Fastlane (+ `match`) vs Codemagic vs other CI-native tooling, weighing setup cost against the solo-dev/small-team context.

(The CI job topology for the `integration_test` run was split out and resolved as ticket 17; whether to build a Flutter-web local test harness was split out and resolved as ticket 18 — this ticket is scoped to signing/release only.)

## Answer

### Starting position

The RN app builds via **EAS Build** (Expo's managed service) through `.github/workflows/eas-build.yml`, with `mobile/eas.json` declaring development/preview/production profiles. All three are `distribution: "internal"` — **there has never been a public store release.** So this is not migrating a release pipeline; it is building the first real one.

EAS silently provides two things that disappear with it:
- **Managed signing credentials** (certs/profiles/keystore held and rotated by Expo).
- **Remote build-number auto-increment** (`appVersionSource: "remote"`, `autoIncrement: true`).

Both `mobile/eas.json` and `.github/workflows/eas-build.yml` delete as part of the port.

### Decision

**Fastlane, scoped to release lanes** (build + upload to TestFlight / Play internal track), **driven from the Mac laptop** rather than wired into CI initially. Free, portable, no vendor lock-in, and it makes releases a reproducible script instead of a remembered sequence of Xcode clicks — while remaining the migration path to CI-driven releases later.

**Skip `match` initially.** Its purpose is syncing certificates across multiple machines/signers; with one Mac and one signer, Xcode-managed signing is adequate. Adopt `match` when a second machine or person needs to sign.

Codemagic was considered and passed over: its main advantage (UI-managed signing, no Ruby toolchain) pays off for teams, and the cost plus lock-in isn't justified for a solo pre-launch app.

⚠️ **Must not be forgotten**: EAS's remote build-number auto-increment needs an explicit replacement — either a Fastlane `increment_build_number` step, or a `pubspec.yaml` version plus a CI/locally-supplied build number. Easy to overlook until the first duplicate-build-number store rejection.
