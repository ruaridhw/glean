# Maestro E2E Testing & CI Pipeline — Design Spec

**Date:** 2026-04-11
**Status:** Draft

## Overview

Replace Detox with Maestro for end-to-end testing of the Glean mobile app. Add E2E tests to the existing GitHub Actions PR pipeline running on an Android emulator.

## Motivation

- Maestro is framework-agnostic — drives the compiled APK without native build hooks, better Expo compatibility
- YAML-based flows are simpler to write and maintain than Detox's JS test harness
- Easier CI setup — no Detox-specific Jest runner, global setup/teardown, or test environment wiring
- Android emulator on GitHub Actions with caching provides a free, self-contained E2E pipeline

## Test Migration

### Tests to port (6 flows)

**smoke.yaml** — Launch, tab navigation, and pantry CRUD
- Verify all 5 tabs are visible, and only 5 tabs are visible.
- Navigate to each tab and assert heading text
- Add item via manual entry (FAB → Manual Entry → fill name/quantity → save)
- Verify item appears in pantry list

**screens.yaml** — All main screens render key elements
- Pantry: heading and FAB visible
- Meals: heading, "My Recipes" and "Discover" toggles visible
- Plan: "This Week" heading and "Generate week" button visible
- Shop: "Shopping List" heading visible
- Settings: "Settings" heading visible

**empty-states.yaml** — Empty state UI on all tabs
- Launch with cleared app data (`clearState` in Maestro)
- Pantry: empty state with "Scan receipt" and "Describe items" CTAs
- Meals: empty state with "Search recipes" CTA
- Plan: empty state with "No meals planned this week"
- Shop: empty state with "Go to meal plan" CTA
- Verify "Describe items" CTA navigates to describe screen

**toasts.yaml** — Toast notification after pantry item added
- Add item via manual entry
- Assert "Added to pantry" text appears

**scan-progress.yaml** — Scan screen loads
- Navigate to scan via pantry FAB or empty state CTA
- Handle camera permission prompt if shown
- Verify scan screen renders

**error-states.yaml** — Offline banner and API error handling
- Toggle airplane mode via `adb shell cmd connectivity airplane-mode enable`
- Assert offline banner appears with expected text
- Restore connectivity, assert banner disappears
- Navigate to recipe search, disconnect, submit search
- Assert error state and "Try again" button visible
- Restore connectivity

### Tests skipped (2)

**animations.test.ts** — Verifying animation behavior and list transitions requires React Native internal synchronization. Not blackbox-testable.

**skeleton.test.ts** — Skeleton shimmer placeholders are transient loading states that disappear within milliseconds. Unreliable to catch in blackbox testing.

## Maestro Flow Structure

```
mobile/
├── e2e/
│   ├── smoke.yaml
│   ├── screens.yaml
│   ├── empty-states.yaml
│   ├── toasts.yaml
│   ├── scan-progress.yaml
│   ├── error-states.yaml
│   └── helpers/
│       ├── launch.yaml          # clearState + launchApp
│       └── navigate-tab.yaml    # Tap tab by testID (parameterised)
```

### Selector strategy

The app already has `testID` props on key elements. Maestro accesses these on Android via the `id` selector:

```yaml
- tapOn:
    id: "tabs.pantry"
```

For elements without testIDs, use text matching:

```yaml
- tapOn: "Manual Entry"
- assertVisible: "Added to pantry"
```

### Helper flows

**launch.yaml** — Called at the start of each flow via `runFlow`:
```yaml
appId: com.ruaridhw.glean
---
- clearState: com.ruaridhw.glean
- launchApp: com.ruaridhw.glean
```

**navigate-tab.yaml** — Parameterised sub-flow:
```yaml
appId: com.ruaridhw.glean
---
- tapOn:
    id: "tabs.${tab}"
```

Called as:
```yaml
- runFlow:
    file: helpers/navigate-tab.yaml
    env:
      tab: pantry
```

### Network toggling for error-states

Maestro does not have a built-in network toggle. The error-states flow will use `runScript` to execute adb commands:

```yaml
- runScript:
    script: |
      const result = java.lang.Runtime.getRuntime().exec("adb shell cmd connectivity airplane-mode enable")
      result.waitFor()
```

Alternatively, this can be wrapped in a helper shell script called via Maestro's `runScript`. This is the most fragile flow — if it proves unreliable in CI, it can be removed without affecting the other 5 flows.

## CI Pipeline

### Architecture

The E2E job runs in parallel with the existing lint and test jobs in `mobile-ci.yml`. All three jobs trigger on PRs touching `mobile/**`.

```
mobile-ci.yml
├── lint     (Ubuntu, ~1 min)
├── test     (Ubuntu, ~2 min)
└── e2e      (Ubuntu, ~10-15 min)
    ├── Checkout
    ├── Enable KVM
    ├── Setup Node 22 + npm cache
    ├── npm ci
    ├── Setup Java 17 + Gradle cache
    ├── AVD cache (API level 35, Pixel_10_Pro)
    ├── Create AVD snapshot (cache miss only)
    ├── expo prebuild --platform android
    ├── Gradle assembleDebug
    ├── Install Maestro CLI
    ├── Start emulator → maestro test e2e/
    ├── Upload screenshots on failure
    └── Done
```

### Caching strategy (3 layers)

**1. AVD snapshot cache**
- Key: `avd-35`
- Path: `~/.android/avd/*, ~/.android/adb*`
- Saves ~1-2 min of AVD creation and first-boot time
- Only recreated when API level changes

**2. Gradle build cache**
- Via `gradle/actions/setup-gradle@v4`
- Caches compiled dependencies and build outputs
- Saves ~3-5 min on subsequent builds

**3. npm dependency cache**
- Already present in existing CI config
- Key based on `package-lock.json` hash

### Emulator configuration

- API Level: 35 (Android 15, stable and well-supported by emulator runner)
- AVD Profile: Pixel_10_Pro
- Architecture: x86_64
- Options: `-no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -camera-back none`
- Animations disabled for test reliability
- Uses `reactivecircus/android-emulator-runner@v2`

### Failure artifacts

On test failure, Maestro screenshots and logs are uploaded as GitHub Actions artifacts with 14-day retention for debugging.

## Package Changes

### Remove

- `detox` from devDependencies
- `detox.config.js`
- `e2e/jest.config.js`
- All `e2e/*.test.ts` files

### Add

- 6 Maestro flow YAML files + 2 helper files in `e2e/`
- Updated `mobile-ci.yml` with e2e job

### Modify

- `package.json`: Replace `"e2e": "detox test"` with `"e2e": "maestro test e2e/"`

### Unchanged

- App source code — all `testID` props remain as-is
- Unit test setup — `jest.config.js` already ignores `e2e/`
- `eas.json` and build profiles
- `mobile-deploy.yml`

## Local Development

Developers run E2E locally with:

1. Start Android emulator (`adb` / Android Studio)
2. Build and install debug APK (`npx expo run:android`)
3. `npm run e2e` (runs all flows) or `maestro test e2e/smoke.yaml` (single flow)

Maestro CLI is a standalone binary installed via `curl -fsSL "https://get.maestro.mobile.dev" | bash` — not an npm dependency.
