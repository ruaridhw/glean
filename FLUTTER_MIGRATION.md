# Flutter Migration Spec

A locked architecture and migration spec for replacing Glean's Expo/React Native app (`mobile/`) with a native Flutter app targeting iOS and Android.

The Flutter implementation exists at `app/` but has not cut over to production. The original decisions and rejected alternatives live in `.scratch/flutter-port/` (see [Provenance](#provenance)).

## Current contract update — 2026-10-06

The merged #95/#98 backend contract and decisions in #97/#96 supersede the saved-recipe generation assumptions below:

- Generate sends `source: "corpus"`, pantry, dietary flags, purchase tolerance, empty-slot count, cooking-time limit and `exclude_external_ids` for already-planned corpus recipes. Saved recipes remain available for manual planning; `recipe_history` and `food_group_coverage` are optional in corpus mode (AC-PLAN-08 is no longer required there).
- Suggestions carry nullable `recipe_id` and `external_id`; corpus mode does not return `missing_ingredients`. Fetch corpus details, reuse/save the local recipe, then write plan entries and shopping gaps in one guarded transaction. Failed detail fetches are skipped. Generate stays disabled throughout fetching and persistence, tops up only, and reports `No recipes fit right now. Try again.` if no entries were added.
- Shopping parse always proposes items; clarifying questions are optional hints. Each question on Shop review has an answer field. Submit appends answers to the original description and re-parses, preserving edited values and selections for case-insensitive matching original item names. This is review reconciliation, not ingredient-identity matching (#100 remains out of scope).
- Nullable pantry `food_group` no longer causes a server-side 422 (#95). The taxonomy change below is still needed for grouping and expiry, but not for avoiding that old meal-plan bug.

Native builds, iOS/Android visual verification and store cutover remain separate gates; passing headless tests is not device evidence.

---

## 1. Scope

**Big-bang replacement.** The Flutter app reaches feature parity plus the UX corrections below, then the RN app is retired in one cutover. There is no coexistence period, no staged rollout, and no feature-flagging between two clients.

**No data migration.** Local SQLite content (pantry, recipes, meal plans, shopping lists) does not carry over. This is accepted — the app is pre-launch, and every EAS build profile was `distribution: internal`, so **there has never been a public store release**.

**One sanctioned backend change** (§9). Otherwise the FastAPI backend is a frozen contract.

### Out of scope

| Ruled out | Why |
|---|---|
| Coexistence / staged rollout | Big-bang replacement chosen instead |
| Client data migration or export | Data loss on cutover accepted (pre-launch) |
| Dark mode | Real design work (every tone pair needs a dark counterpart); the token-access pattern in §4 keeps it cheap to add later |
| Day-mapped meal slots | Forces decisions about skipped days and drag-reordering — a feature effort, not a port |
| Nutrition display | Stored but unshown; needs design work and the data shape may vary across sources |

---

## 2. Stack

| Layer | Choice | Notes |
|---|---|---|
| Routing | **`go_router`** | Flutter-team published; `StatefulShellRoute.indexedStack` maps directly onto the five per-tab navigation stacks. 3.52M vs 354k weekly downloads against `auto_route`. |
| State | **Riverpod** | The only option with cache/invalidate primitives (`family`, `autoDispose`, `ref.invalidate`, `AsyncNotifier`) analogous to TanStack Query. |
| Persistence | **`drift`** | Best-maintained, SQL-like typed queries closest to the current Drizzle experience. `isar` rejected — maintenance stalled (last stable release ~3 years old). |
| Auth | **`flutter_appauth`** + **`flutter_secure_storage`** | Unchanged identity provider: AWS Cognito Hosted UI federating to Google, PKCE. |
| Networking | **`http`** | The entire remote layer (`GleanApiClient` — recipe search/import, meal-plan generation, the three parse endpoints) is built on it. Omitted from this table originally; a documentation gap, not a stack change (FINDINGS.md/REMEDIATION.md R-06) — `http` shipped from the start. |
| Camera | **`camera`** | Not `image_picker` — receipt scanning needs live preview with a custom framing overlay and programmatic capture. |
| SVG | **`flutter_svg`** | For `GleanMark` from `assets/source/glean-mark.svg`, and for any individually-vendored icon glyph. |
| Permissions | **`permission_handler`** | Plus `Info.plist` strings (`NSCameraUsageDescription`). |
| Splash | **`flutter_native_splash`** | Unifies what are currently two different splash compositions. |
| Haptics | **built-in `HapticFeedback`** | No package. See §7 for the one capability this loses. |
| Snackbars | **built-in `ScaffoldMessenger`** | Replaces `react-native-toast-message`. |

**No custom query-caching layer.** An earlier decision assumed one would be needed to replace TanStack Query. It isn't — see §3.

**`RECORD_AUDIO` is vestigial.** The "describe" screens are plain text inputs posting to an NLP endpoint; there is no audio code anywhere in the app. The permission was forward-declared for an unbuilt dictation feature. If dictation is later built, `speech_to_text` fits the stated intent ("dictation can feed the same text later"); `record` if the design becomes server-side transcription. `flutter_sound` is not recommended — the maintainer has posted a staffing warning and its successor has a pending GPL-v3 relicense.

---

## 3. Data layer

**The backend holds no user state.** Its complete route surface is `GET /recipes/search`, `GET /recipes/{id}`, `POST /recipes/import-url`, `POST /meal-plan`, `POST /receipts/scan`, `POST /receipts/describe`, `POST /shopping/parse-description`, `GET /health`, and a dev-only export. There are no user pantry, plan, or shopping endpoints.

So **local SQLite is the sole source of truth for user data, and the backend is a stateless processing service plus a read-only recipe corpus.** There is nothing to sync. Any repository-with-cache-reconciliation layer would solve a problem this app does not have.

### Two clearly-separated roles

1. **Local `drift` reads → Riverpod `StreamProvider` over `.watch()`.** The source of truth for every screen. Because drift streams re-emit whenever the underlying table changes, **mutations need no invalidation call and there is no on-focus reload**. The current `useFocusEffect` → `load()` → `setLoading` → refetch-after-every-mutation dance (in four screens) **deletes itself rather than being ported**. Mutations just write.

2. **Remote API → command providers** (`AsyncNotifier`/`FutureProvider`) returning *ephemeral proposals* the user reviews and then commits into drift. This matches what those endpoints are: transformations, not resources.

**Hard rule: screens never import drift or the API client directly** — always through providers. Today 11 route files reach into `@/db/*` imperatively.

Only `/recipes/search` wants query-style caching (debounced search); `FutureProvider.family` + `autoDispose` covers it.

### Schema change: user scoping

Today only `user_config` is keyed by user. `pantry_items`, `recipes`, `meal_plan_entries` and `shopping_list_items` have **no user column** — so signing in as a different account inherits the previous user's groceries while their settings reset.

**All user-data tables gain a user-scoping column.** Because no data migrates, this is free now and expensive to retrofit. Sign-out therefore need not wipe the database: a different user simply sees their own empty data, and re-authenticating after token expiry doesn't destroy work.

---

## 4. Design system

**Material widgets everywhere on both platforms**, heavily themed. The app renders one identical custom-branded design language (warm oat, brand green, pill shapes, Plus Jakarta Sans) — not platform-adaptive UI. Cupertino-on-iOS would mean two widget vocabularies fighting the brand for no user benefit.

**Map tokens onto `ColorScheme` + `TextTheme`** so built-in Material widgets inherit the brand automatically, with **one `ThemeExtension`** for what doesn't fit those slots (tone pairs like `warningLight`/`warning`, `ink`, `primaryLight`, radius/spacing/shadow scales). Then theme each built-in centrally — `CardTheme`, `IconButtonTheme`, `SegmentedButtonTheme`, `SnackBarThemeData` — **instead of wrapping it in a bespoke widget**. This is the core inversion versus the RN app, which must wrap because RN ships no themed primitives.

**Token access goes through `Theme.of(context)`, never a global const.** The RN app imports a global at every call site; replicating that would make adding dark mode a codebase-wide refactor instead of a second `ThemeData`.

**Icons:** built-in `Icons`, `_rounded` variants. Zero dependency, guaranteed maintained, stylistically compatible now that Material-everywhere is settled; accepts minor glyph drift from today's Ionicons. Where a specific glyph has no acceptable equivalent, vendor that individual SVG from Ionicons' source (MIT) through `flutter_svg`. The `ionicons` pub package was rejected: last published ~3 years ago, 70/160 pub points.

### Delete rather than port

Each of these exists solely to work around a React Native limitation Flutter doesn't have:

| Delete | Replaced by | Why |
|---|---|---|
| `AppText` **and** `scripts/guard-text-imports.mjs` | `TextTheme` | Its own docstring gives the reason: *"React Native picks the weight from the family NAME, not `fontWeight`, so a style with only fontWeight silently renders the system font."* Declare the weight variants once in `pubspec.yaml` and `fontWeight` resolves natively. The custom lint guard goes too. |
| `swipe-delete-row.tsx` (~100 lines of `PanResponder` + `Animated`) and `swipe-action.ts` | `Dismissible` | Built-in threshold and fling handling. |
| `Toast.tsx` + `react-native-toast-message` | `ScaffoldMessenger`/`SnackBar` | |
| `expo-haptics` | `HapticFeedback` | |
| `SkeletonBox`'s manual `Animated.loop` | `TweenAnimationBuilder` | |
| `LayoutAnimation` | Implicit animations / `AnimatedList` | |

### Add the missing primitive

**There is no `Button` in the design system** — only `IconButton`. 12 of 15 route files hand-roll pill-shaped `Pressable` buttons with duplicated styling. The Flutter design system must include themed button widgets (`FilledButton`/`OutlinedButton`/`TextButton` via `*ButtonTheme`, plus a pill-chip variant).

`Badge` is the one primitive likely to stay bespoke: ours is a tinted label pill, closer to Material's `Chip` than its `Badge` (a notification-dot overlay), and `Chip`'s anatomy may fight the design.

### Layout

**Feature-first:** `lib/features/<feature>/` holding the screen, its own `widgets/`, and its providers; shared design system in `lib/design_system/`; the `go_router` table in `lib/router/`. Drop the vestigial `src/screens/` concept (it holds one file today).

Note *why* this changes: expo-router's file-based routing **forced** screens into route files — `app/(tabs)/pantry/index.tsx` is ~400 lines holding four private sub-widgets plus all styles. `go_router`'s declarative route table removes that coupling.

**Extract private sub-widgets into their own classes.** In Flutter this isn't merely tidiness as it is in React: separate widget classes with `const` constructors get independent rebuild scopes, making it a performance property.

---

## 5. Auth

Unchanged flow: Cognito Hosted UI → Google, PKCE, custom-scheme redirect `glean://auth/callback`.

- **Keep the custom URL scheme.** Universal links / app links would be more RFC-8252-aligned, but require hosting domain-verification files — disproportionate to add to this port's critical path. Deferred (§10).
- **Clear tokens explicitly on logout.** iOS Keychain items survive app uninstall/reinstall, so reinstall-as-signout is not a valid assumption.
- **On token expiry, keep local data readable** behind a "signed out" banner gating only AI-backed features. All user data is local; hard-booting the user out of readable data for a network-only concern is the wrong trade. Today nothing signs out or routes anywhere on expiry.

### Test bypass: separate entrypoint, not a flag

The current CI bakes `EXPO_PUBLIC_AUTH_BYPASS=true` plus the production API URL into a `gradlew assembleRelease` APK and uploads it as an artifact. `EXPO_PUBLIC_*` values are compile-time inlined.

**This is not currently exploitable** — every LLM-backed router applies `dependencies=[Depends(verify_cognito_token)]` at router level, so that build opens into the UI but cannot call any production AI endpoint. No breach or cost-abuse vector.

But the protection rests *entirely* on the backend, and nothing structurally prevents those vars being set on a production profile. **In Flutter the bypass lives in a separate `main_e2e.dart` entrypoint so the bypass path cannot compile into a production binary at all**, plus a startup assertion that it is unreachable against a production API base URL.

---

## 6. UX decisions

Grouped by flow. Each entry is a change from current behaviour unless marked *(unchanged)*.

### Cross-cutting

- **Swipe-only deletes** (`Dismissible`), one gesture per row. Today Pantry, Shop **and** Plan each carry two delete affordances on the same row.
- **Undo snackbar on every destructive action** rather than a confirm dialog — fewer taps and recoverable. Includes **"Cooked"**, which currently decrements pantry quantities irreversibly and silently; this requires storing the delta to reverse it.
- **A short, skippable first-run setup** capturing dinners/week, servings and dietary flags, ending by pointing at receipt-scan. There is no onboarding today, so these values — which drive meal-plan quality — stay at defaults forever. Settings copy must also state that they steer generation, give the cooking-time field a "minutes" unit, and surface its 1–480 bound before it's violated.

### Pantry

- **Expiry is inferred automatically** from per-category shelf life. Today expiry drives badges, the "N expiring" chip and the Plan nudge — but **nothing ever writes an expiry date**; the UI ships as a shell. Depends on §9.
- **All three intake modes behind a `+` sheet** (Scan / Describe / Manual), available whether the pantry is empty or full. Today nothing routes to `add.tsx` at all and Describe is reachable *only* from the empty state, so it vanishes once the user owns one item. Manual entry is dead code.
- **Intake becomes a modal task** — tab bar hidden across scan → progress → review, with explicit cancel. Today the tab bar renders over the camera and a mid-scan tab tap **silently loses the capture**.
- **One review screen, not two.** `shop/review.tsx` and `pantry/review.tsx` do the same job with different looks, different button verbs, and inconsistent numeric fallbacks.
- **Honest progress** — replace three fake time-based steps with a real indeterminate indicator plus timeout and cancel, removing ~2.3s of artificial delay added *after* the API returns.
- **Quantity editing moves to a sheet** covering quantity + unit + expiry with explicit Save/Cancel and real validation. Inline blur-commit silently discards invalid input, can't change units, and has no expiry path.

### Meals

- **The library becomes deliberately curated.** Tapping a search result **previews** it rather than silently saving it forever; the dead bookmark icon in the detail header becomes the **real save/unsave toggle**; saved recipes become **deletable** (no `deleteRecipe` exists anywhere today, so the library can only grow). Deleting a recipe keeps any plan entry referencing it — it snapshots what you're cooking — and just loses the link.
- **Surface `not_suitable_for`** (allergen-ish) prominently. It is stored and displayed nowhere; withholding it from someone deciding what to cook is the one omission here with real-world consequences.
- **Surface `source_url`** as tappable attribution for imported recipes.
- Show the **dish name** in the detail header, not a static "Recipe".
- One search affordance: a real inline input in the Search segment, dropping both the fake search pill and the separate pushed screen.
- After "Add to plan", **stay on the recipe** with a snackbar and reflect state on the button ("In plan"). Check plan-full/already-planned **before** navigating — today the user is sent to Plan and *then* told it's full.
- Add real empty and no-results states to search; make import dedupe as search does, saying "already saved" rather than silently.

### Shop

- **Checkout stops deleting unmatched items.** Today `completeCheckout` deletes every checked row regardless of receipt match: check off 12 items, scan a receipt matching 4, and the other 8 vanish without ever becoming pantry stock. Only rows the receipt actually resolved are removed.
- **Add an explicit "Done shopping"** so a receipt-less trip can complete. Today checkout is reachable *only* through the camera, so a cart otherwise persists indefinitely.
- **Manual items resolve to an ingredient identity on entry.** They currently store `ingredient_id: null`, the root cause of manual items never matching a receipt — while checkout was nonetheless deleting them.
- Scope `checkOffByIngredientIds` properly — it currently ticks off *every* row with a matching ingredient, including ones the user deliberately left unchecked.
- Announce plan-derived shopping rows (silently inserted today); remove a planned meal's rows when the meal is deleted; unify "N checked" / "N items in cart" / "In your cart"; pin the add-item field (it currently scrolls out of view as a list header).

### Plan

- **Week-scoped with week pagination.** Today "This Week" has *no date filter*, `planned_date` is written but never read, cooked meals occupy slots forever, and capacity is gated on **lifetime** entry count — so after a few weeks "Plan full" blocks every add, permanently. Week pagination finally makes `planned_date` load-bearing.
- **Cooked meals stay visible** in their week but stop counting toward "left to plan".
- **Uncooked meals roll forward** into the new week. Rollover must be idempotent (no duplicate-insert on repeat). A meal uncooked for several weeks keeps rolling — per-week capacity naturally limits accumulation.
- **Generation stays top-up only** *(unchanged)* — it fills empty slots and never replaces existing entries. Rejecting a plan wholesale means deleting meals individually, acceptable now that deletes carry undo.
- Note two currently-dead features found here: `preferred_servings` is configurable but ignored (`addMealPlanEntry` hardcodes `servings: 1`), and `food_groups`/`food_group_coverage` are hardcoded empty, making the backend's "balance food group coverage" prompt rule permanently inert.

### Settings & auth

- **Auto-save** — persist each control on change (debounced; on slider release, which also fixes the every-drag-frame re-render). Removes the dirty-state trap where live-updating stats made unsaved state *look* saved while switching tabs discarded edits silently.
- **Terms and Privacy must become real tappable links** before store submission — plain text today.
- Landing tab stays **Pantry** *(unchanged)*; Google-only sign-in stands *(unchanged)*.
- Surface DB-init failure instead of ignoring it — the app currently proceeds with a possibly unusable database.

---

## 7. Haptics & transitions

### A semantic three-weight ladder

Applied **at the design-system level** so screens can't forget it. Weight signals consequence, not decoration.

| Weight | Used for |
|---|---|
| `selectionClick()` | Tab switch, segment switch, filter chip, dietary chip, slider steps |
| `lightImpact()` | Default acknowledgement for any tappable |
| `mediumImpact()` | Committing a data change: confirm, save, add-to-plan, mark-cooked, delete-commit |

`heavyImpact()` and `vibrate()` unused.

**Flutter has no notification-style haptic** (success/warning/error) — the built-in API offers only impacts, `selectionClick`, and `vibrate`. This costs nothing: `hapticNotify` exists in the RN app and is **never called anywhere**, so dropping it is zero-regression and no package is needed. Success/failure is communicated by the snackbar plus a `mediumImpact()`.

Gaps this closes, all silent today: **"Sign in with Google"** — the most important tap in the app; sign-in success and sign-out; the camera shutter; scan success/failure; both review confirms; the Generate tap **and generation completion**, the highest-value moment in the app; swipe-delete commit; filter-chip selection; every tab switch; slider steps. It also fixes tap-delete buzzing **twice** today.

### Transitions

- **Skeleton → content cross-fades** (`AnimatedSwitcher`), never a hard cut. Standardise on skeletons everywhere — recipe detail currently uses a bare spinner while lists use skeletons.
- **Animated list mutations** for insert and remove, and the gap left by a `Dismissible` animates closed. Only Pantry animates at all today.
- **Animate the Plan progress ring** — it is fully static, so it *teleports* from 0/5 to 5/5 after generation. Likewise transition the "Cooked?" pill → checkmark swap.
- **Stop using `replace` where the user is conceptually going back** — `shop/review.tsx` replaces to Shop, so returning slides *forward* and leaves `describe` in the stack with stale text.
- **One splash composition** via `flutter_native_splash`. Today the native splash hands over to a *different* JS splash composition (same green, different layout) with an unanimated pop, then to the tab tree with no fade.

---

## 8. Build, release & CI

### Signing and release

**Fastlane release lanes, driven from the Mac laptop** — build plus upload to TestFlight / Play internal track. Not wired into CI initially. Free, portable, no vendor lock-in, and makes releases a reproducible script rather than a remembered sequence of Xcode clicks.

**Skip `match` initially** — its purpose is syncing certificates across machines/signers; with one Mac and one signer, Xcode-managed signing is adequate. Adopt it when a second signer exists. Codemagic was passed over: its UI-managed signing mainly pays off for teams.

**EAS goes away entirely** — `mobile/eas.json` and `.github/workflows/eas-build.yml` both delete. It was silently providing two things:

1. Managed signing credentials.
2. **Remote build-number auto-increment** (`appVersionSource: "remote"`, `autoIncrement: true`) — needs an explicit replacement, either a Fastlane `increment_build_number` step or a `pubspec.yaml` version plus a supplied build number. Easy to overlook until the first duplicate-build-number rejection.

### CI topology

Two separate jobs under one `workflow_dispatch`-gated workflow — **not** one combined macOS job:

| Job | Runner | Target |
|---|---|---|
| iOS integration | macOS | iOS Simulator |
| Android integration | Linux (KVM) | Android emulator |

Neither runs on push. Both are separate from the Linux runner doing lint/typecheck/unit/widget tests.

**Why not one macOS job:** GitHub-hosted macOS runners cannot run the Android emulator — nested virtualization is unsupported on current arm64 macOS images, and a January 2026 request to lift this was closed "not planned". `ReactiveCircus/android-emulator-runner` now recommends avoiding macOS for Android emulation entirely; Linux/KVM is faster and cheaper regardless.

**Both must also run locally from a single Mac.** Real Apple Silicon hardware isn't subject to that limitation, so one Mac can drive both an iOS Simulator and an Android emulator directly for pre-release verification.

### Flutter web: deferred, benchmark-gated

**Do not build a web harness as committed infrastructure.** It was only ever a candidate *local* dev-loop convenience — worth building if driving Chrome proves meaningfully faster than driving a real emulator for an agent's test-and-iterate loop. That can't be measured before a Flutter app exists.

Once a minimal app runs, time agent-driven Chrome against agent-driven emulator for a representative interaction. Build it only if Chrome wins meaningfully; otherwise skip it entirely.

The setup, if built: `flutter drive -d web-server` with a version-matched `chromedriver` in headless Chrome, phone viewport via `--web-browser-flag="--window-size=390,844"`. Note `flutter test --platform chrome` is **not** the right tool — Flutter's tooling marks it deprecated/internal. Caveat: `defaultTargetPlatform` resolves to the *host* OS on web (Linux in CI), so platform-adaptive gestures, theming, and native plugins are not faithfully exercised — largely mitigated by choosing Material-everywhere (§4).

---

## 9. The one sanctioned backend change

**The parse endpoints must return `category` (and therefore `food_group`) per parsed ingredient.**

Nothing in the app currently assigns an ingredient category: `resolveOrCreateIngredient` is called without one, and `ParsedIngredient` has no such field because the backend doesn't return it. So every user-added ingredient gets `category: null` → `food_group: null` → bucketed as `"other"`. Only the 10 seeded staples have real categories.

That single gap breaks **three** features at once:

1. **Pantry grouping and filter chips** collapse to one "Other" bucket.
2. **Historical meal-plan generation 422s** — fixed by #95: the backend accepts nullable `food_group`. This is no longer a reason to require classification before generation.
3. **Expiry inference has no basis** — per-category shelf life needs a category.

Scope: `POST /receipts/scan`, `POST /receipts/describe`, and `POST /shopping/parse-description` return a category drawn from the **existing** 23-category taxonomy — not a new vocabulary. The LLM already identifies each ingredient while parsing, so classifying it is nearly free. Once categories are reliable, `food_group` stops being nullable client-side and the 422 failure mode disappears.

**This must ship before or with the port**, since the Flutter client depends on it for three features.

Rejected: client-side categorisation by name lookup (means shipping and maintaining a food taxonomy in the app, and still misses unusual ingredients); dropping grouping for a flat list (discards a real feature and leaves expiry inference baseless).

---

## 10. Testing

**Buckets:** 50 Jest files → **28 unit / 14 widget / 1 integration / 7 dropped**. 11 Maestro files → `smoke.yaml` becomes the single `integration_test` suite, 3 fold into widget tests, 5 helpers dropped.

### Biggest leverage: a real in-memory database

**No existing test touches a real SQLite database.** A `chain()`-Proxy fake query-builder plus `makeDbMock(selectQueue)` is **copy-pasted into five files**, and these tests assert *query-builder call shapes* (`expect(mockDb.update).toHaveBeenCalledTimes(1)`) rather than data outcomes. There is no shared test infrastructure at all — no `setupFiles`, no `__mocks__`, no snapshots; every file re-declares its mocks.

One **`drift` `NativeDatabase.memory()` fixture** lets nearly all 12 db-layer tests become real-outcome assertions — shorter, stronger, and collapsing five harnesses into one.

Also: every screen test shims `useFocusEffect` purely to make the manual reload pattern fire. That shim and its reason both **disappear** with drift `.watch()` (§3).

### Dropped outright

| File | Why |
|---|---|
| `shop/use-swipe-action.test.ts` | Tests exactly the threshold mechanism `Dismissible` replaces |
| `tests/platform/haptics.test.ts` | Asserts `expo-haptics` call args; superseded by the §7 ladder |
| `tests/db/client.test.ts` | Tests drizzle migrator memoization — library plumbing |
| `tests/navigation/shop-routing.test.tsx` | Asserts the expo-router file-route table shape |
| `src/__tests__/screens/SplashScreen.test.tsx` | Style-prop assertions; `flutter_native_splash` leaves no widget |
| `tests/flows/receipt-checkout.test.ts` | **Tautological** — the test body reimplements the branch it claims to verify, so it cannot fail for an app-code reason |
| `tests/auth/ci-auth-bypass.test.ts` | Regex over a CI YAML whose env vars all disappear — replaced by a build-level guarantee |

Plus individual cases: the three screen-test swipe cases (each hand-builds a `touchHistory`), `useReviewList`'s "lazy initializer matches `useState`", and the `GestureHandlerRootView` wrapper assertion.

**Highest-value unit ports:** `normalization/units.test.ts`, `meal-plan/compress.test.ts`, `meals/presentation.test.ts`, `db/shopping.test.ts` (shortfall maths), `plan/presentation.test.ts`, `settings/presentation.test.ts`, `auth/mode.test.ts`.

### New coverage this spec requires

Porting alone would leave every decision above untested. The first two are non-negotiable — they're the changes where a regression silently loses or leaks user data:

1. **Checkout keeps unmatched items** — a receipt resolving 4 of 12 checked rows removes exactly those 4.
2. **User-scoped data isolation** — user A's data invisible to user B on the same device.
3. **Undo** on every destructive action, incl. "Cooked" reversing its pantry delta.
4. **Week-scoped queries, pagination, and rollover idempotency**; capacity is per-week not lifetime.
5. **Expiry inference from category**, and that parsed ingredients **persist** their category (§9).
6. **Preview-not-save** on search-result tap; recipe deletion.
7. **Auto-save** of settings.
8. **Production builds cannot include the auth bypass** — startup assertion plus a CI check that release builds use `main.dart`.
9. **The haptic ladder** applied at design-system level.
10. **`go_router` route-table structure.**

`manual/error-states.yaml` (airplane-mode toggling) stays a **manual pre-release checklist item** — it is already excluded from CI. The checklist itself lives at `docs/pre-release-checklist.md`, which also covers the two `integration_test` platform runs and first-release signing/build-number steps.

No test debt from deletions: there is no test for `guard-text-imports.mjs` or `AppText`.

---

## 11. Known bugs — must not reproduce

Found during review, in the app being replaced. Not fixed there (it's being deleted); recorded so the Flutter version doesn't inherit them.

**Data integrity**
- Checkout deletes checked shopping rows the receipt never matched — silent data loss (§6).
- `checkOffByIngredientIds` ignores checked-state and scope, ticking off rows the user deliberately left.
- `add_recipe_id` is never cleared and the re-add runs inside `useFocusEffect`, so leaving the Plan tab and returning **re-adds the recipe every time** — duplicate plan entries *and* duplicate shopping gaps.
- Meal-plan `onSuccess` awaits inserts with no try/catch; React Query's `onError` doesn't fire for a throw inside `onSuccess`, so a bad `recipe_id` half-writes the plan and the user sees *nothing happen*.
- Receipt review's save is non-atomic: a failure on row 3 of 5 leaves rows 1–2 persisted, and because upsert *increments*, retrying **doubles** quantities.
- Generate isn't disabled while pending; a double-tap overfills past `meals_per_week` from stale state.
- Pantry-only review unconditionally mutates the shopping list.

**Dead ends and hangs**
- `scan-progress`'s `fetch`/`blob` isn't wrapped in try/catch and isn't a mutation error — a failure hangs on "Almost done…" forever with no back button and no timeout.
- Camera permission-denied and pending branches have **no back affordance** — a hard dead end after a permanent deny.
- Cold-start deep link to a missing recipe calls `router.back()` with nothing to pop → permanent spinner.
- Any DB error while adding a shopping item leaves the add button **permanently disabled** with no error shown (`setAdding(true)` with no `try/finally`).
- Unguarded `JSON.parse` on nav params white-screens a route with no back button.

**Silent failures**
- `saveUserConfig` failure shows the user nothing — no success, no error.
- Capture failures in the camera are silent; `takePictureAsync` throwing is uncaught.
- DB-init failure is caught and ignored; the app proceeds with a possibly unusable database.
- `refreshTokens` writes a possibly-undefined access token while `hasTokens()` stays true.

**Input handling**
- Decimal quantities are untypeable on **both** review screens (`String(quantity)` ↔ `Number(value)` round-trip); non-numeric input persists as `NaN`.
- Zero/NaN quantities pass validation — Confirm can write `0 units`.
- Inconsistent numeric fallbacks between the twin review screens (one falls back to `1`, the other to `0`).

**Correctness / polish**
- Deleting the last item of a filtered pantry category strands the list — blank body, no chip selected.
- Skeleton flashes on every tab focus in three screens (`loading = true` set unconditionally on focus).
- Sliders write state every drag frame with no `onSlidingComplete` — likely jank.
- `CheckoutBar` floats ~90px above the screen bottom, leaving a dead band.
- Recipe detail uses `useEffect([id])` not `useFocusEffect`, so "to buy" badges go stale.
- `getRecipeByExternalId` skips `attachDietaryFlags`, unlike its siblings.
- iOS sign-in: `promptAsync()`'s return value is dropped, so the flow depends on the redirect arriving as a deep link. `ASWebAuthenticationSession` returns it to `promptAsync` instead — **verify on device**; if it doesn't emit, iOS sign-in dead-ends silently.

---

## 12. Deferred follow-ups

Post-port improvements, each with a ticket in `.scratch/flutter-port/issues/`:

| # | Item |
|---|---|
| 19 | Migrate the OAuth redirect to universal links / app links, once a production domain exists |
| 21 | Prompt mid-checkout for unmatched items ("keep or remove?") rather than leaving them |
| 23 | User-settable / correctable expiry — inferred shelf life will sometimes be wrong |
| 24 | Surface generation `reason` + `missing_ingredients`; pre-flight guard for empty pantry / no saved recipes / offline; **plus the missing client timeout on the LLM call**, which is the cheapest piece and could land earlier |

---

## Provenance

Every decision traces to a resolved ticket under `.scratch/flutter-port/`:

- `map.md` — the effort's index, destination, and decision log
- `issues/NN-*.md` — one ticket per decision, each with its question, answer, rejected alternatives, and file-level evidence
- `issues/_cross-cutting.md` — decisions spanning multiple flows
- `research/` — sourced research notes (routing/state/persistence, auth, camera/audio, Flutter-web test target, build/CI), each committed on its own branch; see the corresponding ticket for the branch name

UX findings were gathered by reading all five flows end to end; file:line citations live in tickets 11–15. The test inventory (tickets 16) enumerates all 61 test files individually.
