# Mobile Replit Reconciliation Design

## Summary

This project reconciles the working Replit mobile prototype in `mobile_replit/` with the real Expo app in `mobile/`.

The Replit version is the target visual and UX direction. The real `mobile/` app remains canonical for data, backend integration, and auth. Navigation depth, production flows, tests, e2e coverage, and build-chain choices are open to change after comparison. The goal is not to copy the prototype wholesale. The goal is to port the useful design, interaction polish, and product ideas onto the real app architecture, while using the comparison to improve questionable mobile app and build-chain decisions.

The first implementation phase should be low-risk: produce an audit matrix, make explicit build-chain and dependency decisions, add a small shared UI foundation, and then port Pantry as the first proof screen.

## Goals

- Compare `mobile/` and `mobile_replit/` screen by screen.
- Treat Replit as the visual/UX target unless there is a concrete reason to diverge.
- Keep the existing real database, backend, auth, and production semantics as canonical.
- Identify Replit-only features and classify them as port now, adapt now, defer, or reject.
- Evaluate build-chain choices such as npm vs pnpm, single app vs workspace, dependency resolution, scripts, and CI ergonomics without assuming the current chain must stay.
- Add a small reusable visual foundation before changing screens.
- Port Pantry first as the proof-of-port using real SQLite/Drizzle data and intentionally chosen flows after comparison.
- Optimize Android and iOS as first-class platforms, with Android explicitly checked for adopted polish and web supported with graceful fallbacks.

## Non-goals

- Do not port Replit's hard-coded data, seed state, or `AsyncStorage` app state into `mobile/`.
- Do not rewrite every screen in one implementation phase.
- Do not replace the real backend, DB schema, or auth flow merely to match prototype shortcuts.
- Do not adopt every Replit dependency automatically.
- Do not design a large component library before validating the primitives against a real screen.

## Canonical source rules

`mobile/` is canonical for:

- SQLite + Drizzle schema and migrations.
- FastAPI/backend integration.
- Cognito auth flow.

The following are not canonical by default and must be compared against the Replit prototype:

- App navigation depth and production flows.
- Test strategy and test coverage shape.
- e2e coverage expectations.
- Lint/typecheck/pre-commit/build-chain expectations.

These areas may move toward the Replit version, stay closer to `mobile/`, or become a third better design after comparison. The implementation plan should not preserve them by inertia.

`mobile_replit/` is canonical for:

- Target visual direction.
- Interaction polish.
- Screen presentation patterns.
- Replit-only product ideas that may be worth porting.

Hard rule: no Replit state model or hard-coded data should be copied into the real app as production state. Every Replit UI idea must be adapted onto the real app's DB queries, API calls, hooks, and navigation.

## Recommended approach

Use a foundation-first reconciliation approach.

1. Audit both apps.
2. Classify features, screens, dependencies, and build-chain differences.
3. Decide what to port, adapt, defer, or reject.
4. Build a small shared UI foundation.
5. Port Pantry as the first proof screen.
6. Verify Android first, then iOS and web fallbacks.
7. Use the Pantry result to guide later Meals, Plan, Shop, and Settings work.

This balances visible progress with discipline. It avoids copying prototype assumptions into the real app and gives a learning artifact explaining why each technical decision was made.

## Platform policy

Android and iOS are first-class platforms. Android is an explicit optimization target. Web should continue to work as a graceful fallback, but web preview needs should not dominate native decisions.

Native polish should be classified as:

- Cross-platform default: works well on Android and iOS and can become the standard behavior.
- Platform enhancement: valuable on one platform, guarded behind platform checks, with clean fallbacks elsewhere.
- Deferred polish: visually nice but too unstable, too platform-specific, or too costly for the first phase.

No adopted polish may be required for correctness. If haptics, blur, symbols, or modal presentation are unavailable, the app must still behave correctly.

## Dependency policy

Adopt dependencies when they improve real mobile UX or implementation quality and pass Android/iOS viability checks.

Likely candidates to adopt or expand:

- `expo-haptics` for tactile feedback, with safe no-op fallback where unavailable.
- `@expo/vector-icons` / Ionicons / MaterialCommunityIcons for replacing emoji tab icons and improving screen action affordances.
- Platform-appropriate modal/page-sheet conventions, with Android and web fallbacks.
- `expo-blur` only if Android behavior is acceptable and the effect is nonessential.
- `expo-image` later if recipe imagery becomes important.

Likely caution or defer items:

- `expo-router/unstable-native-tabs` until Android behavior and route compatibility are proven.
- `expo-glass-effect` as optional iOS enhancement only, not a baseline requirement.
- Replit's `AsyncStorage` context state model, because the real app uses SQLite/Drizzle.

## Build-chain policy

The current `mobile/` build chain is not protected by default. It should be compared against the Replit setup and other standard Expo practices.

The audit should compare:

- npm vs pnpm.
- Single package vs workspace layout.
- Lockfile reliability and dependency resolution.
- Expo compatibility.
- CI and local setup ergonomics.
- Makefile integration.
- Test, lint, typecheck, Knip, and highest-level smoke/e2e strategy.
- Whether a workspace would help future backend/mobile/shared package organization.

If pnpm or a workspace materially improves reliability, speed, dependency hygiene, or future organization, the implementation plan may include migrating to it. If the current npm setup is simpler and equivalent for this repo, keep it and document why. The decision should come from explicit comparison, not inertia.

## Audit matrix

The first implementation task should produce a matrix that compares `mobile/` and `mobile_replit/`.

For each screen:

- Current real app route and file path.
- Replit prototype route and file path.
- Navigation and flow differences.
- Visual patterns to port.
- Interaction patterns to port.
- Features present in both.
- Features only in Replit.
- Features only in `mobile/`.
- Data assumptions made by Replit.
- Real DB/API fields available in `mobile/`.
- Decision: port, adapt, defer, or reject.
- Testing impact.

Screens to compare:

- Pantry.
- Meals.
- Plan.
- Shop.
- Settings.

The same matrix style should be used for dependencies and build-chain choices.

## Shared UI foundation

Before porting Pantry, add only the primitives needed to express the Replit visual direction across more than one screen.

Initial foundation scope:

- Theme expansion: color roles, spacing, typography, radius, shadows, muted/card/background semantics, and dark-mode hooks if needed.
- Screen scaffold: safe-area-aware header, optional subtitle/actions, consistent bottom-tab padding, and platform-aware top spacing.
- Card/list primitives: card container, row layout, section label, metadata row, grouped list section.
- Chip/badge primitives: category chips, unit chips, selected/unselected states, and urgency badges.
- Action primitives: icon button, primary/secondary pill action, and floating add button if it still fits after comparison.
- Modal/sheet convention: reusable wrapper with platform-appropriate presentation and keyboard-safe scroll behavior.
- Icon/haptic wrapper: centralize direct calls so platform fallbacks are consistent.

Keep the foundation small. If a primitive is only needed by one screen and not clearly reusable, keep it local until a second screen needs it.

## Pantry proof-of-port

Pantry is the first screen to port after the audit and foundation work.

Pantry should:

- Keep existing real pantry queries and mutation functions.
- Compare existing flows for scanning receipts, describing items, manual add, quantity edits, deletion, and any Replit alternatives; preserve, adapt, or replace them intentionally.
- Move toward Replit's visual treatment: large header, cards, category indicators, chips, polished actions, and modal/sheet presentation where appropriate.
- Map real `food_group`, ingredient, quantity, and unit data to the Replit-style category presentation.
- Add expiry badges only if supported by real data, or explicitly defer the required schema/API work.
- Preserve only the highest-level smoke/e2e coverage needed to prove the app still launches and core navigation works. Do not spend migration effort maintaining detailed e2e coverage screen by screen.
- Validate Android behavior before treating the port as successful.

## Feature reconciliation rules

Each Replit-only feature must be classified before implementation.

Decision categories:

- Port now: valuable, compatible with existing SQLite/backend model, low risk.
- Adapt now: valuable UX, but must be rewired to real DB/API/navigation.
- Defer: good idea, but needs schema/backend/API work or more product thought.
- Reject: hard-coded prototype convenience, worse UX, or not aligned with the real app.

Likely candidates to evaluate:

- Pantry category chips, expiry badges, richer add-item modal, recipe quick-view from expiring ingredients.
- Meals saved/suggested toggle, recipe detail modal, save/bookmark interaction.
- Plan weekly navigation, dinners-per-week progress, generate shopping list from plan.
- Shop grouped categories, checked/unchecked sections, move checked items to pantry.
- Settings stats, dinners-per-week, default servings, dietary preferences, waste alerts, clear data.

Schema changes are allowed when justified, but they must go through Drizzle migrations and tests. Backend changes are allowed only when needed for real app behavior, not just to mimic prototype data.

## Error handling and states

Preserve real-app behavior while improving presentation.

- Loading states should use existing skeleton patterns restyled toward the new visual foundation.
- Empty states should keep real actions such as scan receipt, describe items, and add manually.
- DB/API failures should use existing `ErrorState` and toast patterns unless a native alert is clearly better.
- Destructive actions should use platform-native confirmation dialogs where appropriate.
- Haptics should be best-effort and ignored if unavailable.

## Testing and verification

The first implementation phase should include:

- Lower-level tests for data mapping, date/expiry logic if introduced, real DB integration boundaries, and component state where practical.
- Mobile Jest or integration tests for shared primitives and key Pantry behavior when they catch meaningful regressions.
- Highest-level smoke/e2e coverage only: verify the app launches and core navigation still works. Ignore detailed e2e migration work during this phase unless a smoke test is broken.
- Android emulator verification for Pantry proof-of-port and any native polish dependency.
- iOS verification for platform-specific enhancements when available.
- Web fallback check if the changed code affects web execution.
- `make test-mobile` and `make lint-mobile` unless the build-chain migration changes the commands, in which case the Makefile should be updated first.

## Rollout

The rollout should be incremental:

1. Produce the comparison/audit matrix.
2. Decide build-chain and dependency changes explicitly.
3. Add or adjust the shared UI foundation.
4. Port Pantry as the proof screen.
5. Verify Android first, then iOS and web fallbacks.
6. Use the Pantry result to plan Meals, Plan, Shop, and Settings.

The full all-screen visual port should not be bundled into the first implementation phase. Pantry validates the approach before broader rollout.

## Open implementation decisions for the plan

These should be resolved during implementation planning, not guessed during coding:

- Whether to migrate `mobile/` from npm to pnpm.
- Whether the repo should become a pnpm workspace now or later.
- Which Replit dependencies are adopted in phase one.
- Whether expiry badges require schema/API work or should be deferred.
- Whether Pantry keeps the floating add button, moves add actions into the header, or uses both.
- Which exact shared primitives are created before Pantry and which remain local.
