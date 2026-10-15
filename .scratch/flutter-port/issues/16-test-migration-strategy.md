Type: grilling
Status: resolved
Blocked by: 06, 08

## Question

Given the stack decision (ticket 06) and component-architecture decision (ticket 08), produce the test-migration strategy and classification for every current test:

- Every Jest/RTL suite under `mobile/tests/` and `mobile/src/__tests__/` — classify as: ports to a Flutter unit test, ports to a Flutter widget test, or **drop** (tests an implementation detail or behavior that won't exist post-port — don't default to porting everything).
- Every Maestro flow under `mobile/e2e/` (`empty-states.yaml`, `scan-progress.yaml`, `screens.yaml`, `smoke.yaml`, `toasts.yaml`, plus `e2e/manual/error-states.yaml`) — classify as: folds into a Flutter widget test, becomes part of the single cross-platform `integration_test` suite (ticket 09's manual macOS CI job), or **drop**.

Cross-check classifications against any closed UX-review tickets (11–15) — a test covering behavior that a UX review changed should be re-scoped or dropped, not ported as-is. Produce the concrete list (not just the methodology) as the deliverable.

## Answer

Full inventory taken: **50 Jest files** (10 under `src/__tests__/`, 40 under `tests/`) and **11 files under `e2e/`** (5 CI flows, 1 manual flow, 5 helpers).

### Headline: the biggest leverage point is a real in-memory database

**No existing test touches a real SQLite database.** There are three hand-rolled mocking styles, and a `chain()`-Proxy fake drizzle query-builder plus `makeDbMock(selectQueue)` is **copy-pasted into 5 files** (`tests/db/plan.test.ts`, `tests/db/shopping.test.ts`, `tests/db/shopping-mutations.test.ts`, `tests/flows/receipt-checkout.test.ts`, `tests/meals/pantry-match.test.ts`). Consequently these tests assert *query-builder call shapes* (`expect(mockDb.update).toHaveBeenCalledTimes(1)`) rather than data outcomes.

A single **`drift` `NativeDatabase.memory()` fixture** lets nearly all 12 db-layer tests be rewritten as real-outcome assertions — shorter, stronger, and collapsing five duplicated harnesses into one shared fixture. There is currently no shared test infrastructure at all: no `setupFiles`, no `__mocks__` directory, no snapshot tests; every file re-declares its own mocks.

Second infrastructure note: every screen test shims `useFocusEffect: (cb) => React.useEffect(cb, [cb])` purely to make the manual reload pattern fire under test. That shim — and the reason for it — **disappear** with [ticket 20](20-decide-data-layer-architecture.md)'s drift `.watch()` streams.

### Buckets

**Jest (50): unit 28 · widget 14 · integration 1 · DROP 7.**
**Maestro (11): integration 3 · widget 3 · DROP 5.**

**Highest-value unit ports** (pure logic, no mocking pain): `normalization/units.test.ts` (kg→g, L→ml, cup-of-flour→g via density), `meal-plan/compress.test.ts` (urgency scoring + top-N compression), `meals/presentation.test.ts`, `db/shopping.test.ts` (shortfall calculation across servings), `plan/presentation.test.ts`, `settings/presentation.test.ts`, `auth/mode.test.ts` (security logic — keep).

**DROP outright (7 files):**
| File | Why |
|---|---|
| `shop/use-swipe-action.test.ts` | Tests exactly the threshold mechanism `Dismissible` replaces (ticket 08) |
| `tests/platform/haptics.test.ts` | Asserts `expo-haptics` call args; superseded by ticket 10's design-system ladder |
| `tests/db/client.test.ts` | Tests drizzle/expo-sqlite migrator memoization — library plumbing |
| `tests/navigation/shop-routing.test.tsx` | Asserts the expo-router file-route table shape; no analogue |
| `src/__tests__/screens/SplashScreen.test.tsx` | Style-prop assertions; `flutter_native_splash` (ticket 10) leaves no widget to test |
| `tests/flows/receipt-checkout.test.ts` | **Tautological** — the test body reimplements the `returnTo === "shop"` branch it claims to verify, so it cannot fail for an app-code reason |
| `tests/auth/ci-auth-bypass.test.ts` | A regex over a CI YAML whose Expo env vars all disappear — but see "replacement coverage" below |

**Individual cases to drop inside otherwise-kept files:** the swipe cases in `pantry/pantry-screen.test.tsx`, `plan/plan-screen.test.tsx`, and `shop/shop-screen.test.tsx` (each drives `onResponderGrant/Move/Release` with a hand-built `touchHistory`); `intake/useReviewList.test.ts`'s "lazy initializer matches `useState`" (React-hook semantics); and `navigation/root-layout.test.tsx`'s `GestureHandlerRootView` wrapper assertion.

**Merge:** `src/__tests__/db/shopping.test.ts` and `tests/db/shopping-mutations.test.ts` both cover `addManualShoppingItem`.

**Split:** `intake/serialization.test.ts` exists mainly because expo-router serialises nav params to strings. With `go_router` passing typed objects the round-trip becomes moot; the **stable `review_id` identity assignment is still real logic** and ports.

### Maestro e2e

- **`smoke.yaml` → THE single Flutter `integration_test` suite** (ticket 17: macOS runner → iOS Simulator, Linux/KVM runner → Android emulator, both `workflow_dispatch`-gated). Launch, five tabs visible, navigate each, add an item. Note its "add item via manual entry" path *works again* now that ticket 11 makes manual entry reachable via the `+` sheet — it was dead code.
- **`screens.yaml`, `empty-states.yaml`, `toasts.yaml` → widget tests.** All three are redundant with the four screen tests' existing cases; `toasts.yaml` becomes a `SnackBar` widget test.
- **`scan-progress.yaml`** — camera-permission handling folds into the integration suite.
- **`manual/error-states.yaml`** (airplane-mode toggling) — stays a **manual pre-release checklist item**, not automated. It is already excluded from CI.
- **DROP all 5 helpers**: `launch.yaml` is pure Expo Go dev-client choreography (clearState, Metro `openLink`, dismissing the Expo Go overlay, swiping away the dev menu); `navigate-tab.yaml` is a one-liner; `grant-camera-permission.yaml` gets reimplemented inside `integration_test`; both airplane-mode JS helpers go with `error-states`.

### Replacement and NEW coverage required by this effort's decisions

Porting alone would leave the newly-decided behaviour untested. These are **new** tests, and the first two are non-negotiable — they are the two changes where a regression silently loses or leaks user data:

1. **Checkout keeps unmatched items** ([ticket 13](13-ux-review-shop.md)) — assert that scanning a receipt resolving 4 of 12 checked rows removes exactly those 4 and leaves the other 8 on the list. Also assert `checkOffByIngredientIds` no longer ticks off rows outside scope.
2. **User-scoped data isolation** ([cross-cutting](_cross-cutting.md)) — assert user A's pantry/recipes/plan/shopping are invisible to user B on the same device.
3. **Undo snackbar** on every destructive action (pantry item, shopping row, plan entry, and "Cooked" reversing its pantry delta).
4. **Week-scoped plan queries + week pagination** ([ticket 14](14-ux-review-plan.md)) — including that cooked meals stay visible but don't count toward "left to plan", and that capacity is per-week not lifetime (the current lifetime-count lockout).
5. **Expiry inference from category** ([ticket 11](11-ux-review-pantry.md)) and that parsed ingredients **persist their category** ([ticket 22](22-decide-ingredient-categorisation.md)) — the latter guards the fix for three separate broken features.
6. **Preview-not-save** on tapping a search result, and recipe deletion ([ticket 12](12-ux-review-meals.md)).
7. **Auto-save** of settings ([ticket 15](15-ux-review-settings-auth.md)).
8. **Production build cannot include the auth bypass** — replaces the dropped `ci-auth-bypass.test.ts` with something stronger: the bypass lives in a separate `main_e2e.dart` entrypoint (ticket 15), so assert via a startup assertion plus a CI check that release builds use `main.dart`. A build-level guarantee, not a unit test.
9. **Design-system haptic ladder** applied per ticket 10 — replaces the dropped `haptics.test.ts` at the right level.
10. **`go_router` route-table structure** — replaces the dropped `shop-routing.test.tsx` intent with an analogue that actually exists in Flutter.

### Judgement calls made

- **`tests/auth/redirect-uri.test.ts`** — keep. Ticket 07 retained the custom scheme, so the cross-repo contract (`glean://auth/callback` must appear in `backend/template.yaml`) still holds. Better expressed as a CI lint than a unit test, but the check earns its place.
- **`tests/navigation/root-layout.test.tsx`** — auth gating is the most integration-worthy behaviour in the suite, but it is cheaply expressible as a **widget** test with a fake auth provider, and far faster. Chosen: widget.
- **`tests/auth/session.test.tsx`** — renders a `Pressable` harness only to read provider state; with Riverpod this is a **unit** test of a notifier.
- **`tests/db/seed.test.ts`** — asserts *23 categories and 10 staples* by counting `runAsync` calls containing SQL substrings. Port the intent ("seeded DB contains the expected categories/staples") against the in-memory drift fixture; drop the brittle call-count style.
- **`src/__tests__/api/hooks.test.ts`** — mocks react-query so completely that only the trim/validate wrapper is exercised. Ticket 20 removes the TanStack layer, so port only the trim/validate logic as a unit test.
- **`PlanSkeleton.test.tsx`** — kept as a widget test: skeletons survive ticket 10 (cross-fade), even though drift `.watch()` collapses the manual loading window.

### No test debt from deletions
There is **no test** for `mobile/scripts/guard-text-imports.mjs` or for `AppText` — the font-family enforcement runs only via `npm run check`. Deleting both (ticket 08) leaves nothing behind.
