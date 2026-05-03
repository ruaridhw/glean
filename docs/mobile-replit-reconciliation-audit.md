# Mobile/Replit Reconciliation Audit

## Phase-one decision summary

- Source of truth for data/backend/auth: `mobile/`.
- Visual and UX target: `mobile_replit/artifacts/meal-planner`.
- Navigation and flow policy: compare first; keep or change intentionally.
- Build-chain phase-one decision: keep `mobile/` on npm for the Pantry proof-of-port. Re-evaluate pnpm/workspace after Pantry validates the UI approach.
- Dependency phase-one decision: add `expo-haptics`; keep existing `@expo/vector-icons`; defer `expo-blur`, `expo-glass-effect`, `expo-image`, and `expo-router/unstable-native-tabs`.
- Test strategy: use lower-level Jest/integration tests for presentation and Pantry behavior; keep only highest-level smoke/e2e coverage.

## Why npm stays for phase one

The Replit project uses a pnpm workspace because it manages generated artifacts, a mock API server, workspace-local packages, and Replit-specific dev scripts. The current Glean repo has one JS app under `mobile/` and a Python backend managed by `uv`. There is not yet a shared TypeScript package or multiple real JS packages that require workspace coordination. Migrating npm to pnpm during the first UI proof would mix tooling migration risk with UI migration risk. The decision is to defer pnpm/workspace migration until after the Pantry proof or until a shared JS package is introduced.

## Screen comparison matrix

| Screen | mobile/ path | Replit path | Visual/UX target | Real data source | Phase-one decision |
| --- | --- | --- | --- | --- | --- |
| Pantry | `mobile/app/(tabs)/pantry/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/index.tsx` | Large header, cards, category dots, expiry badges, polished add/delete/edit actions | `getPantryItems`, `updatePantryQuantity`, `deletePantryItem` | Port now as proof screen |
| Meals | `mobile/app/(tabs)/meals/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/meals.tsx` | Saved/suggested tabs, recipe cards, detail modal | real recipe DB/API | Defer until after Pantry |
| Plan | `mobile/app/(tabs)/plan/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/plan.tsx` | Weekly navigation, progress, shopping list generation | real meal plan DB | Defer until after Pantry |
| Shop | `mobile/app/(tabs)/shop/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/shop.tsx` | Grouped checked/unchecked list, move checked to pantry | real shopping DB | Defer until after Pantry |
| Settings | `mobile/app/(tabs)/settings/index.tsx` | `mobile_replit/artifacts/meal-planner/app/(tabs)/settings.tsx` | Stats, preferences, clear data UI | real config DB/auth | Defer until after Pantry |

## Pantry data mapping

| Replit concept | Real mobile field/source | Decision |
| --- | --- | --- |
| `item.name` | `PantryItem.canonical_name` | Adapt now |
| `item.quantity` | `PantryItem.quantity` | Adapt now |
| `item.unit` | `PantryItem.unit` | Adapt now |
| `item.category` | `PantryItem.food_group ?? "other"` | Adapt now with display metadata |
| `item.expiryDate` | `PantryItem.expiry_date` | Port now; schema already supports it |
| Add item modal | Existing add route with scan/describe/manual choices | Keep route flow for phase one; restyle later |
| Recipe quick view from expiring items | Requires recipe suggestion wiring | Defer |

## Dependency comparison

| Dependency/pattern | Replit usage | Phase-one decision | Reason |
| --- | --- | --- | --- |
| `expo-haptics` | Button feedback | Adopt | Low risk, Android/iOS support, optional wrapper prevents correctness dependency |
| Vector icons | Rich tab/action icons | Adopt/expand existing dependency | `@expo/vector-icons` already exists in `mobile/` |
| `expo-blur` | Tab/background polish | Defer | Not required for Pantry proof; Android behavior should be checked separately |
| `expo-glass-effect` | iOS glass polish | Defer | iOS enhancement only, not Android-first baseline |
| `expo-router/unstable-native-tabs` | Native tabs | Defer | Route compatibility and Android behavior need separate proof |
| pnpm workspace | Replit artifact/workspace management | Defer | Not justified before a shared JS package or multi-package JS repo need |

## Test strategy

- Add pure tests for Pantry presentation mapping.
- Add component tests for reusable UI primitives.
- Add a focused Pantry screen test with mocked DB functions.
- Keep highest-level smoke/e2e coverage only; do not chase detailed e2e updates unless the smoke path breaks.

## Pantry proof verification

- Android manual check date: 2026-05-02
- Android SDK/ADB setup: REPAIRED locally. `/Users/ruaridhw/Library/Android/sdk` now has platform tools, emulator, Android 35 platform/build tools, an Android 35 ARM system image, and a `glean_api35` AVD.
- Android launch result: PARTIAL. `make start-android` now starts Metro, opens the emulator, installs Expo Go, and reaches the app launch step, but Expo CLI's `adb shell monkey` launcher exits with code 251 on this emulator. Direct `adb shell am start ... exp://10.0.2.2:8081` reaches the JS bundle.
- Android manual Pantry result: DEFERRED. Further ADB/emulator runs were skipped for this pass; the latest emulator attempt exposed an Expo Go/native dependency mismatch around `ExpoCryptoAES`, so the package alignment was completed and verified by tests/lint, but the manual Pantry checklist still needs a fresh emulator pass.
- Highest-level smoke/e2e result: BLOCKED locally because the Maestro CLI is not installed (`npm run e2e -- e2e/smoke.yaml` exits with `maestro: command not found`).
- Unit/integration result: PASS (`make test-mobile`: 23 suites, 92 tests passed).
- Lint/typecheck result: PASS (`make lint-mobile`: Biome, TypeScript, and Knip exited 0; Knip emitted configuration hints only).
- Follow-up items:
  - Restart Metro with a clean cache and relaunch Expo Go via `exp://10.0.2.2:8081`, then run the Pantry manual checklist.
  - If `ExpoCryptoAES` still appears after package alignment, reinstall Expo Go on the emulator or use a development build with the app's native modules.
  - Install Maestro, then rerun `cd mobile && npm run e2e -- e2e/smoke.yaml`.
  - Evaluate Meals saved/suggested UX after Pantry visual direction is accepted.
  - Revisit pnpm/workspace after a second screen or shared JS package need emerges.
  - Evaluate blur/native tabs/glass effects in a separate platform-polish spike.
