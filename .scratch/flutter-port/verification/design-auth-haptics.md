# Verification: Section C (AC-DS-*), Section D (AC-AUTH-*), Section K (AC-HAP-*/AC-TRN-*)

Verifier: independent agent, did not implement any of this code.
Verified against `app/` at HEAD `906c9bb` ("🔥 refactor: delete the Expo/React Native app").
`flutter analyze` → 0 issues. `flutter test` → 345/345 passing, 0 skipped, at the start
and end of this session.

Methodology: read every file cited below directly; for criteria claimed by a specific
test, ran the test, then temporarily broke the guarded behaviour in place to confirm the
test fails, then reverted. All such edits are reverted — `git status`/`git diff` are
clean at the end of this report (confirmed at the bottom).

---

## C. Design system

**AC-DS-01 — CONFIRMED.** `grep -rn cupertino lib` → no hits. `theme.dart:323` forces
`Typography.material2021(platform: TargetPlatform.iOS, ...)` unconditionally (not
`Platform`-branched), so typography doesn't even vary by host OS — reinforces
"Material everywhere," not platform-adaptive.

**AC-DS-02 — CONFIRMED.** Exactly one class extends `ThemeExtension`:
`lib/design_system/tokens.dart:119` (`class AppTokens extends ThemeExtension<AppTokens>`).
The other two `ThemeExtension` hits are a usage site (`lerp`'s parameter type) and the
`extensions: const <ThemeExtension<dynamic>>[AppTokens.standard]` registration in
`theme.dart:107` — not additional subclasses. `AppTokens` carries exactly what §4
specifies: `ink`, `primaryLight`, the `warning`/`warningLight` tone pair, and the
`radius`/`spacing`/`shadow` scales (`tokens.dart:120-140`).

**AC-DS-03 — CONFIRMED, with a minor adjacent note.** `grep -rn` for a top-level
`const Color`/style constant anywhere under `lib/features/` returns nothing, and no
feature file imports `design_system/theme.dart` (the file that owns the brand hex
literals) — only `design_system/design_system.dart`, the token/helper barrel. Every
`Color`/`TextStyle` read in `lib/features/**` goes through `Theme.of(context)` or
`context.tokens`.

Adjacent, not a violation of the letter: `lib/features/intake/widgets/camera_permission_prompt.dart:24`
and `lib/features/intake/scan_screen.dart:114` both write `const Color(0xFF111511)`
as a **local literal** (the camera viewfinder backdrop) — not an import of a global
const, so it doesn't trip this criterion's specific prohibition, but it is a raw hex
value with no token backing it (it doesn't match `tokens.ink` either, `0xFF26362B`).

**AC-DS-04 — CONFIRMED.** `theme.dart` centrally themes `cardTheme` (109), `iconButtonTheme`
(121), `filledButtonTheme`/`outlinedButtonTheme`/`textButtonTheme` (130/143/155),
`segmentedButtonTheme` (166), `chipTheme` (194), `snackBarTheme` (215), `inputDecorationTheme`
(226), `appBarTheme` (249), `navigationBarTheme` (260), `dividerTheme` (288). No
`Glean*Card`/`Glean*IconButton`/`Glean*SegmentedButton` wrapper class exists anywhere
(`grep` empty) — built-ins are themed, not wrapped.

**AC-DS-05 — CONFIRMED.** The button primitive is the themed built-ins
(`FilledButton`/`OutlinedButton`/`TextButton` via `*ButtonTheme`, `theme.dart:130-164`)
plus the pill-chip variant (`chipTheme`, `theme.dart:190-211`, explicitly commented
as "The pill-chip variant of the missing Button primitive (AC-DS-05)"). `grep -rn
GestureDetector lib` → **zero hits anywhere in `lib/`**. Every `InkWell` in
`lib/features/**` wraps a `Card`/row as a tappable list item, not a hand-rolled
button: `pantry_item_row.dart:32`, `search_result_card.dart:21`, `recipe_card.dart:30`,
`recipe_detail_view.dart:163`, `shopping_row.dart:25`, `plan_slot_row.dart:48/98`. The
one exception, `scan_overlay.dart:85` (`Material(shape: CircleBorder(), child: InkWell(...))`),
is the camera shutter — a circular control with no Material "shutter" equivalent, not
a pill shape, not styled as a button. No survivor of the RN pattern found.

**AC-DS-06 — PARTIAL.** 68 of 75 `Icons.*` references in `lib/` use `_rounded`. Seven
use `_outlined` with no vendored-SVG exception claimed:
- `lib/router/app_shell.dart:19,24,29,34,39` — `eco_outlined`/`restaurant_outlined`/
  `calendar_month_outlined`/`shopping_cart_outlined`/`settings_outlined` as the
  bottom-nav's *unselected* icon, each paired with a `_rounded` `selectedIcon` on the
  same `NavigationDestination` — a defensible Material selected/unselected convention,
  but the unselected glyph itself is not `_rounded` and the criterion's letter doesn't
  carve out an exception for this.
- `lib/features/settings/widgets/legal_links_section.dart:30,37` —
  `description_outlined`/`privacy_tip_outlined` as plain `ListTile` leading icons, no
  selected-state pairing to justify the variant.
- `lib/features/shop/widgets/shop_states.dart:22` — `shopping_cart_outlined` as the
  empty-state illustration icon, same — no pairing, no SVG exception.

**AC-DS-07 — PARTIAL.** `GleanMark` does render from the vendored SVGs via
`flutter_svg` (`lib/design_system/brand_mark.dart:47`, `SvgPicture.asset(...)`) —
confirmed by pumping a bare `GleanMark()` in a throwaway widget test; it builds and
`find.byType(GleanMark)` finds it. But FINDINGS.md F-01 is **still live, not resolved**:
all three vendored SVGs still contain `<filter>` elements —
`assets/brand/glean-b1-icon.svg:12`, `glean-b1-adaptive-foreground.svg:7`,
`glean-b1-splash-logo.svg:12` — and `flutter_svg: ^2.3.0` (pubspec.yaml) still cannot
render them. Reproduced live: the same throwaway test printed
`unhandled element <filter/>; Picture key: Svg loader` to the console on every pump.
This silently drops the authored drop-shadow and spams the log on every real screen
that mounts `GleanMark()` — confirmed two such screens exist:
`lib/features/auth/sign_in_screen.dart` and `lib/features/onboarding/onboarding_screen.dart:192`.
Not a crash, but exactly the "silent visual regression... spams the console" F-01
describes, and nothing in this port addressed it.

**AC-DS-08 — CONFIRMED.** `grep -rn "class AppText" lib` → no hits (only a doc-comment
mention in `theme.dart:41` explaining why it's gone). `grep -rn "guard.*text\|guard_text"`
across the whole repo → no hits; no such script exists.

**AC-DS-09 — CONFIRMED.** `SwipeToDeleteRow` (`lib/design_system/swipe_to_delete.dart`)
wraps built-in `Dismissible` only. `grep -rn "PanResponder\|onPanUpdate\|onHorizontalDrag\|velocity"
lib` → the only hits are doc-comment prose describing the *deleted* RN mechanism, no
actual gesture/threshold code anywhere.

**AC-DS-10 — CONFIRMED.** `lib/design_system/snackbar.dart`'s `GleanSnackBar` is two
static methods wrapping `ScaffoldMessenger.of(context)`/`SnackBar` — no queue, no
bespoke toast widget.

**AC-DS-11 — CONFIRMED.** `SkeletonBox` (`lib/design_system/skeleton.dart`) drives its
pulse entirely with `TweenAnimationBuilder`/`setState` in `onEnd` (lines 44-55).
`grep -rn AnimationController lib` → zero hits anywhere in `lib/`.

**AC-DS-12 — CONFIRMED.** `GleanBadge` (`lib/design_system/badge.dart:11-24`) is the
only bespoke label-pill primitive, and its doc comment explicitly justifies it against
both close built-ins (`Badge`'s notification-dot anatomy, `Chip`'s interactive
anatomy). The design system's other custom widgets (`GleanCrossFade`, `SkeletonBox`,
`SwipeToDeleteRow`, `GleanMark`) are thin wrappers *around* a stock built-in
(`AnimatedSwitcher`, `TweenAnimationBuilder`, `Dismissible`, `SvgPicture`) mandated by
other criteria, not reinvented primitives, so they don't compete with this one.

**AC-DS-14 — PARTIAL.** No file under `lib/features/**` exceeds ~250 lines (largest:
`settings_screen.dart` at 249, `presentation.dart`/`meals` at 244 — measured directly
with `wc -l`, sorted). But `lib/features/onboarding/onboarding_screen.dart:95`
(`Widget _buildStep()`) and `:142` (`Widget _buildFooter(AppTokens tokens)`) are
exactly the forbidden pattern — private sub-widget builder **methods** on the State
class, not extracted widget classes. `grep -rn "^\s*Widget _[a-zA-Z]" lib/features` →
these are the *only* two hits in the entire tree; every other screen (verified
`settings_screen.dart` in full, and spot-checked `pantry_screen.dart`, `plan_screen.dart`)
correctly extracts sub-widgets into their own `const`-constructible classes. A
narrow, isolated violation, not a systemic one — but it is real and it is exactly what
the criterion names.

**Notable, not one of my ACs but discovered while checking AC-DS-14:**
`lib/features/onboarding/onboarding_gate.dart` — the widget that's supposed to show
`OnboardingScreen` on first run — is never referenced anywhere in `lib/router/router.dart`
or any entrypoint (`grep -rln OnboardingGate lib` → only its own definition file).
The entire first-run onboarding flow (AC-UX-04, section E) is built and independently
tested but **structurally unreachable** in the running app. Flagging for whoever owns
section E/AC-UX-04, and because it's the reason `onboarding_screen.dart` was even in
scope for my AC-DS-14 check.

---

## D. Auth

**AC-AUTH-01 — CONFIRMED.** `lib/auth/cognito_auth_client.dart:44` — `redirectUri =
'glean://auth/callback'`, matches `backend/template.yaml:102`'s `CallbackURL` exactly;
`test/auth/redirect_uri_contract_test.dart` asserts this directly and passes.
`signIn()` (lines 61-77) calls `flutter_appauth`'s `authorizeAndExchangeCode` with
`identity_provider: 'Google'` — Google-only via Cognito Hosted UI. PKCE is not an
explicit toggle in this `flutter_appauth`/`flutter_appauth_platform_interface` version
(no `usePKCE` parameter exists in the platform interface) — it is the default,
implicit behaviour of the underlying native AppAuth SDK for the authorization-code
grant, so there is nothing in this codebase that could disable it.

**AC-AUTH-02 — CONFIRMED.** `lib/auth/token_storage.dart`'s `SecureTokenStorage` is
the only token-persistence implementation, backed by `flutter_secure_storage`
(`pubspec.yaml:41`). `grep -rn "shared_preferences\|SharedPreferences" lib pubspec.yaml`
→ no hits; no alternative storage path exists.

**AC-AUTH-03 — CONFIRMED.** `AuthController.signOut()` (`auth_controller.dart:216-219`)
calls `_requireStorage.clearAll()` explicitly, which deletes every stored key including
identity (`token_storage.dart:114-115`). `test/auth/auth_controller_test.dart`'s
"signOut AC-AUTH-03: clears storage explicitly and moves to signedOut" passes.

**AC-AUTH-04 — PARTIAL.** The session-state half is solid and tested: a failed refresh
moves to `AuthStatus.expired` while **keeping** `userId` (`auth_controller.dart:238-243`),
and the router's redirect explicitly only fires for `signedOut` — `lib/router/router.dart`'s
`_authRedirect`, with its own comment: "AC-AUTH-04: redirect gates on `signedOut` only.
`expired` deliberately falls through untouched." Confirmed passing:
`test/auth/auth_controller_test.dart`'s "AC-AUTH-05 / AC-AUTH-04: a failed refresh
moves to expired, keeps the user id, and never persists an empty/partial token."

But the UI half — "behind a signed out banner that gates only AI-backed features" —
is **dead code**. `lib/features/auth/widgets/signed_out_banner.dart` defines
`SignedOutBanner` and reads `aiFeaturesAvailableProvider`; `grep -rn "SignedOutBanner("
lib/features` and `grep -rn aiFeaturesAvailableProvider lib` both return **only that
one file's own definition** plus one isolated widget test
(`test/features/auth/signed_out_banner_test.dart`). No screen — not the Scan flow, not
either Describe screen, not the Generate button, not the recipe-import screen — mounts
`const SignedOutBanner()` or reads `aiFeaturesAvailableProvider` to disable itself. The
widget's own doc comment says exactly where it belongs ("Feature screens that offer an
AI-backed action (Scan/Describe/Import/Generate) should mount `const SignedOutBanner()`
near the top of their body") but no wave actually did it. In the shipped app, an
expired session shows no banner anywhere and does not gate any AI action —
those actions will simply attempt their network call and fail with whatever generic
error each screen already has, giving the user no indication *why*.

**AC-AUTH-05 — CONFIRMED.** `CognitoAuthClient.refresh()` (`cognito_auth_client.dart:121-161`)
returns `null` — never throws, never returns a partial token — both when the platform
call itself fails and when it structurally succeeds but the access/id token is
null/empty. `AuthController.getValidAccessToken()` (`auth_controller.dart:225-257`)
only calls `_requireStorage.saveTokens(refreshed)` after confirming `refreshed != null`;
on `null` it calls `clearTokensKeepIdentity()` instead of leaving a stale token. Both
branches are directly tested in `cognito_auth_client_test.dart` ("AC-AUTH-05: returns
null (never throws...)" and "...for a structurally-successful response with an
empty/missing access token — the exact RN bug this must not reproduce") and pass.

**AC-AUTH-06 — CONFIRMED, verified by mutation.** Added `import 'auth/auth_bypass.dart';`
to `lib/app.dart` (which `main.dart` transitively imports via `bootstrap.dart`), ran
`test/auth/auth_bypass_test.dart` — the "AC-AUTH-06: no file under lib/ other than
auth_bypass.dart itself..." test failed with `Actual: ['lib/app.dart']`, confirming the
test is not vacuous. Reverted the edit; `git diff` on `lib/app.dart` is empty (confirmed
below). The check is a full-text scan of every `.dart` file under `lib/` for an
import/export naming `auth_bypass.dart`, which is sound for Dart's static import graph
(every link in a transitive chain is necessarily a literal import/export statement
somewhere) — not merely a check on `main.dart` itself.

**AC-AUTH-07 — CONFIRMED.** `test/build/release_entrypoint_test.dart` scans the actual
build configuration (not the Dart source graph) — `ios/fastlane/Fastfile`,
`android/fastlane/Fastfile`, and every `.github/workflows/*.yml` — for any line that is
both a release-build invocation (`flutter build`/`gradlew assemble*`/`bundle*`) and
mentions `main_e2e`. All four sub-tests pass at HEAD.

**AC-AUTH-08 — CONFIRMED.** `CognitoAuthClient.signIn()` (`cognito_auth_client.dart:61-77`)
awaits `_gateway.authorizeAndExchangeCode(...)` and consumes its **returned** result
directly — no deep-link listener. `grep -rn "uni_links\|app_links\|getInitialLink"
lib pubspec.yaml` → no hits; no such package or listener exists anywhere.

---

## K. Haptics & transitions

**AC-HAP-01 — CONFIRMED.** `lib/design_system/haptics.dart:31-35` — `abstract class
Haptics` exposes exactly `selectionClick`/`lightImpact`/`mediumImpact`.

**AC-HAP-02 — CONFIRMED.** `heavyImpact`/`vibrate` are not members of the `Haptics`
interface at all (not merely unused-but-present — unreachable through the design
system by construction). `grep -rn "HapticFeedback" lib` → the only real calls are
`haptics.dart:44,49,54` (`selectionClick`/`lightImpact`/`mediumImpact` only).
`test/design_system/haptics_test.dart` additionally source-scans `haptics.dart` for
`HapticFeedback.heavyImpact`/`.vibrate` and asserts absence; passes.

**AC-HAP-03 — CONFIRMED, verified by mutation.** Added a second
`ref.read(hapticsProvider).mediumImpact();` call inside `SwipeToDeleteRow`'s
`onDismissed` (`swipe_to_delete.dart:63-66`), ran
`test/design_system/swipe_to_delete_test.dart` — "a single swipe-to-delete fires
exactly one haptic (AC-HAP-03)" failed (`Expected: [medium]`, `Actual: [medium, medium]`).
Reverted; diff clean. Also structurally: `grep -rn "Icons.delete" lib/features` →
zero hits outside `SwipeToDeleteRow`'s own `_DeleteReveal` background, so no other
delete affordance exists anywhere that could independently double-fire (this also
corroborates AC-UX-01's "exactly one delete affordance" claim, not one of my ACs but
relevant evidence).

**AC-HAP-04 — CONFIRMED.** `grep -rn "HapticFeedback" lib/features` → zero hits. Every
haptic call site in feature code goes through `ref.read(hapticsProvider)`.

**AC-HAP-05 — PARTIAL.** Checked each of the twelve named moments individually rather
than accepting the summary claim:

| Moment | Status | Evidence |
|---|---|---|
| Google sign-in tap | CONFIRMED | `sign_in_screen.dart:30` `lightImpact()` |
| sign-in success | CONFIRMED | `sign_in_screen.dart:38` `mediumImpact()` |
| sign-out | CONFIRMED | `settings_screen.dart:153` `mediumImpact()` |
| camera shutter | CONFIRMED | `scan_screen.dart:74` `lightImpact()` |
| both review confirms | CONFIRMED | one shared screen, `review_screen.dart:89` `mediumImpact()` |
| scan success/failure | **FAILED** | zero haptic calls anywhere in `scan_progress_screen.dart`, `pantry_describe_screen.dart`, `shop_describe_screen.dart`, `describe_form.dart` (`grep -ic haptic` on each → 0); no test asserts one for this moment either |
| Generate tap | CONFIRMED | `generate_button.dart:66` `mediumImpact()` |
| generation completion | CONFIRMED (success path) | `plan_screen.dart:112` `mediumImpact()` fires on the success branch of a `ref.listen`; the error branch shows a snackbar with no haptic, consistent with the ladder's own philosophy (commit-weight haptics fire on success, not failure) |
| swipe-delete commit | CONFIRMED | `swipe_to_delete.dart:64` `mediumImpact()` |
| filter-chip selection | CONFIRMED | `pantry_filter_chips.dart:30` `selectionClick()` |
| every tab switch | **FAILED** | `lib/router/app_shell.dart`'s `onDestinationSelected` (line 52) fires no haptic; the whole widget is a plain `StatelessWidget` with no `ref`/haptics access at all (`grep -ic haptic app_shell.dart` → 0); no test in `test/router/**` asserts a tab-switch haptic |
| slider steps | CONFIRMED | `integer_slider_control.dart:64`, `tolerance_card.dart:61`, both `selectionClick()` |

Ten of twelve confirmed; two concrete, verifiable misses.

**AC-TRN-01 — PARTIAL.** The dominant, correct pattern — one `Scaffold`, its `body:`
wrapped in `GleanCrossFade` — is used consistently by Pantry (`pantry_screen.dart:43-63`),
Shop (`shop_list_section.dart`), Plan (`plan_screen.dart`), Settings
(`settings_screen.dart`), Meals search (`meals_search_panel.dart`), and
`RecipePreviewScreen`. But `lib/features/meals/saved_recipe_detail.dart:46-65` —
`SavedRecipeDetail.build`'s **outer** `recipeAsync.when(...)` — switches between two
structurally different `Scaffold`s (a skeleton-only `Scaffold(appBar: Text('Recipe'), body:
RecipeDetailSkeleton())` vs. `_SavedRecipeDetailBody`, its own full `Scaffold` titled with
the real dish name) with **no** `AnimatedSwitcher`/`GleanCrossFade` around that decision.
This is a hard cut on every first load of a saved recipe's detail screen (reached from
the Meals list and from a cold-start deep link via `MealDetailScreen`), even though the
*inner* transition inside `_SavedRecipeDetailBody` (ingredients loading) correctly uses
`GleanCrossFade` (`saved_recipe_detail.dart:121`).

**AC-TRN-02 — PARTIAL.** Removal is confirmed animated for free via `Dismissible`'s
built-in resize/fade (the passing baseline of `swipe_to_delete_test.dart` proves the
row physically animates out on commit). But **insertion has no animation anywhere in
the app**: Pantry (`pantry_section_view.dart:52-56`), Shop (`shop_list_section.dart:60-61,66-67`),
and Meals' saved-recipe list (`meals_screen.dart:100-120`) each build their rows with a
plain `for`-loop inside a `Column`/`ListView`. Each carries a doc comment explaining
the choice not to use `AnimatedList` — but every comment addresses only *removal*
("wrapping this in an AnimatedList would fight [Dismissible] with a second removal
animation," verbatim in all three files) — none mentions or provides any insertion
treatment. A newly scanned pantry item, newly added shopping row, or newly saved
recipe appears instantly, with no fade-in/slide-in. (Plan sidesteps this entirely by a
different design — its slot count is fixed per week and only a slot's *content* swaps
via `AnimatedSwitcher`, `plan_slot_row.dart:99,150` — so Plan has no insert/remove of
rows to animate in the first place.)

**AC-TRN-03 — CONFIRMED.** `grep -rn "pushReplacement\|GoRouter.*replace\|\.replace(AppRoutes"
lib` → the only `.replace(` hit anywhere in `lib/` is an unrelated `Uri.replace(...)`
in `api_client.dart:189` (URL query params, not navigation). Cancel/back paths
consistently use `context.pop()`/`context.canPop()` (`scan_screen.dart:96-97`,
`scan_progress_screen.dart:83`, `saved_recipe_detail.dart:159-160`); forward
progression through intake uses `context.pushNamed` (`scan_screen.dart:79`,
`shop_screen.dart:53,61`); landing on a destination after finishing a task (review
confirm, manual-entry save, cross-tab jumps from an empty Plan slot or a deleted
recipe) uses `context.go`/`context.goNamed`. In `go_router`, `go()` re-resolves the
**entire** location and rebuilds the matching route stack from scratch, unlike React
Navigation's `replace()` (which swaps only the top of an existing stack, leaving
everything beneath it — the actual mechanism of the RN bug). So there is no code path
here that can reproduce "returning slides forward and leaves a stale screen in the
stack."

**AC-TRN-04 — CONFIRMED**, for the banner the code itself names against this
criterion. `PantryExpiryBanner` (`pantry_expiry_banner.dart:16-19`) is wrapped in
`AnimatedSwitcher` with distinct `ValueKey`s per state, and its doc comment cites
AC-TRN-04 directly. Adjacent note: the Plan tab's structurally similar nudge
(`PlanExpiryBanner`) has no such wrapper — `plan_screen.dart:167-170` adds/removes it
from the `ListView`'s children via a bare `if (nudge != null) ...`, so it pops in/out
abruptly rather than fading. This is arguably outside the letter of AC-TRN-04 (which
names "the expiry banner," and Pantry's is the one the codebase associates with this
criterion) — flagged below as a defect the criteria set doesn't cleanly assign to
anyone.

**AC-TRN-05 — FAILED**, for the fade. `lib/bootstrap.dart`'s `GleanRoot.build`
(lines 57-69) is:
```dart
return ready.when(
  data: (_) => const GleanApp(),
  loading: () => const _SplashHolding(),
  error: (Object error, StackTrace _) => _DatabaseErrorApp(error: error),
);
```
— a plain branch selection with **no** `AnimatedSwitcher`/`AnimatedOpacity`/
`FadeTransition` wrapping the `loading` → `data` swap. Confirmed by direct reading (no
animation widget exists in the method or anywhere else in the file); corroborated by
the complete absence of any test for this transition (`grep -rln "GleanRoot\|_SplashHolding"
test` → no hits). This is precisely "no unanimated hand-off," the literal defect the
criterion forbids. The "exactly one splash composition" half of the criterion does
hold: the native splash and the Flutter-drawn holding screen both use the identical
flat brand-green fill (`#2E9D63`) with no second logo/layout, so there is no second
*visual* composition — only an unanimated widget swap once the database is ready.
F-01 (the SVG `<filter>` issue) does **not** affect this: the splash asset is a
rasterized PNG (`flutter_native_splash.yaml:24`, "flutter_native_splash requires a
raster PNG, not the SVG directly"), and the Flutter-side holding screen is a flat
`ColoredBox`, not an `SvgPicture` — no `flutter_svg` rendering happens in this path at
all.

---

## Tally

Section C (14 criteria): 10 CONFIRMED, 4 PARTIAL (AC-DS-06, AC-DS-07, AC-DS-14; plus the
already-CONFIRMED AC-DS-03 carries a minor adjacent note), 0 FAILED, 0 UNVERIFIABLE.
Section D (8 criteria): 7 CONFIRMED, 1 PARTIAL (AC-AUTH-04), 0 FAILED, 0 UNVERIFIABLE.
Section K (10 criteria): 5 CONFIRMED, 3 PARTIAL (AC-HAP-05, AC-TRN-01, AC-TRN-02),
2 FAILED-in-part (AC-TRN-05's fade is a clean FAILED; AC-HAP-05 is scored PARTIAL above
but contains two unambiguous FAILED sub-items), 0 UNVERIFIABLE.

Nothing in my assignment required a device/simulator build, so nothing is
UNVERIFIABLE here.

**Most valuable finding — defects no single criterion cleanly covers:**

1. **The Plan-tab expiry nudge doesn't fade** (`lib/features/plan/widgets/plan_expiry_banner.dart`
   + `plan_screen.dart:167-170`), while its Pantry counterpart does. AC-TRN-04 names
   "the expiry banner" and the codebase's own comment ties that phrase to Pantry's
   banner specifically, so this Plan-side inconsistency isn't unambiguously anyone's
   criterion to fail on — but it's the same class of UI element with a visibly
   different (worse) transition treatment right next to the one that got it right.

2. **`OnboardingGate` is never wired into the router** (`lib/router/router.dart` never
   references it; `AppShell` is built directly). This makes the entire first-run
   onboarding flow structurally unreachable despite being fully built and independently
   tested — technically AC-UX-04's failure (section E, not mine), but I'm flagging it
   here because I found it while investigating `onboarding_screen.dart` for AC-DS-14,
   and it's exactly the kind of "built and tested in isolation, never actually reachable"
   gap the whole verification pass exists to catch.

3. **`SignedOutBanner`/`aiFeaturesAvailableProvider` being entirely unmounted means no
   AI-backed action is pre-flight-gated on auth status** — Scan/Describe/Import/Generate
   will each attempt their network call regardless of session state and fail with
   whatever generic error they already show, never a "you're signed out" message. I've
   scored this under AC-AUTH-04 above (PARTIAL) since that's the criterion whose text
   ("gates only AI-backed features") it most directly contradicts, but the deeper
   implication — misleading generic failures with no auth-specific messaging anywhere —
   isn't literally spelled out by that criterion's letter either.

## `git diff` confirmation

All temporary edits made during verification (mutation-testing AC-AUTH-06 on
`lib/app.dart`, AC-HAP-03 on `lib/design_system/swipe_to_delete.dart`, and two
throwaway test files that were created under `test/` and deleted immediately after
use) have been reverted or removed.

```
$ git status
On branch flutter-port
Untracked files:
  (use "git add <file>..." to include in what will be committed)
	../.scratch/flutter-port/verification/
nothing added to commit but untracked files present (use "git add" to track)

$ git diff --stat
(empty)
```

The only untracked item is this report's own directory. `flutter test` (full suite)
passes 345/345 at the end of this session, matching the count at the start.
