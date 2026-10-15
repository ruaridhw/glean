# Flutter Port — Acceptance Criteria

Every criterion below is derived from [`FLUTTER_MIGRATION.md`](../../FLUTTER_MIGRATION.md).
The port is **done** when every box is `[x]`, each ticked by an **independent verifier
agent** (never the agent that implemented it), and a code reviewer raises no
unresolved blocking finding.

## Rules of the loop

- **Implementer ≠ verifier.** A criterion may only be ticked by an agent that did not write the code for it.
- **Evidence required.** Every tick records `file:line` and/or the command whose output proves it. A verifier that cannot produce evidence must leave the box unticked and say why.
- **`[!]` means failed verification** — an implementer must fix it, then a *different* verifier re-checks.
- **Verification runs against a green tree**: `flutter analyze` clean and `flutter test` passing are preconditions for any tick (AC-BUILD-04/05).
- The Flutter app lives at **`app/`**. `mobile/` is kept as read-only porting reference until AC-CUT-01.

Legend: `[ ]` unverified · `[x]` verified by independent agent · `[!]` failed, needs rework

---

## A. Project, build & toolchain (§2, §8)

- [ ] **AC-BUILD-01** A Flutter project exists at `app/` with `flutter create` platform scaffolding for **iOS and Android only** (no web/desktop directories committed).
- [ ] **AC-BUILD-02** `pubspec.yaml` declares exactly the sanctioned stack: `go_router`, `flutter_riverpod`, `drift` (+`drift_dev`, `sqlite3_flutter_libs`), `flutter_appauth`, `flutter_secure_storage`, `camera`, `flutter_svg`, `permission_handler`, `flutter_native_splash`. No `expo`-era leftovers, no `isar`, no `auto_route`, no `ionicons`, no toast package, no haptics package.
- [ ] **AC-BUILD-03** Plus Jakarta Sans weight variants are declared in `pubspec.yaml` `fonts:` and the font files are committed under `app/assets/`.
- [ ] **AC-BUILD-04** `flutter analyze` exits 0 with **zero** errors, warnings, or infos.
- [ ] **AC-BUILD-05** `flutter test` exits 0 with every test passing and none skipped.
- [ ] **AC-BUILD-06** `analysis_options.yaml` enables `flutter_lints` plus `prefer_const_constructors` and `use_super_parameters`; the analyzer excludes generated `*.g.dart`/`*.drift.dart` only.
- [ ] **AC-BUILD-07** drift codegen is reproducible: `dart run build_runner build --delete-conflicting-outputs` succeeds and leaves the tree unchanged (generated files are committed and in sync).
- [ ] **AC-BUILD-08** `flutter_native_splash` is configured (`flutter_native_splash.yaml`) producing **one** splash composition on brand green; the generated native assets are committed.
- [ ] **AC-BUILD-09** Two entrypoints exist: `lib/main.dart` (production) and `lib/main_e2e.dart` (test bypass). No auth-bypass symbol is reachable from `main.dart`'s import graph.
- [ ] **AC-BUILD-10** `Info.plist` carries `NSCameraUsageDescription`; `AndroidManifest.xml` declares `CAMERA` and the `glean` custom-scheme intent filter. **`RECORD_AUDIO` is absent** (§2 — vestigial).
- [ ] **AC-BUILD-11** No Flutter **web** harness is committed (§8 — deferred, benchmark-gated). A benchmark note recording the Chrome-vs-emulator decision exists.

## B. Data layer (§3)

- [ ] **AC-DATA-01** A drift database class defines every table the RN app had: pantry items, ingredients, ingredient categories, recipes, recipe ingredients, dietary flags, meal plan entries, shopping list items, user config.
- [ ] **AC-DATA-02** **Every user-data table carries a user-scoping column** — pantry items, recipes, meal plan entries, shopping list items (not just `user_config`).
- [ ] **AC-DATA-03** Every read query filters by the current user id. No query returns another user's rows.
- [ ] **AC-DATA-04** Reads are exposed as Riverpod `StreamProvider`s over drift `.watch()`. **No screen performs an on-focus/manual reload**, and no `loading` boolean is set on navigation focus.
- [ ] **AC-DATA-05** Mutations perform **no cache invalidation call** — no `ref.invalidate` / `refetch` after a write anywhere in `lib/features/`.
- [ ] **AC-DATA-06** Remote calls are `AsyncNotifier`/`FutureProvider` command providers returning **ephemeral proposals**; nothing from an API response is persisted without an explicit user commit step.
- [ ] **AC-DATA-07** **Hard rule enforced:** no file under `lib/features/**/` imports the drift database or the API client directly — access is via providers only. (Verify by grep across the whole feature tree.)
- [ ] **AC-DATA-08** `/recipes/search` uses `FutureProvider.family` + `autoDispose` with debounce.
- [ ] **AC-DATA-09** Sign-out does **not** wipe the database (§3) — local rows survive and a different user sees only their own.
- [ ] **AC-DATA-10** The 23-category ingredient taxonomy and 10 staples are seeded, verified by querying a real in-memory DB (not by counting SQL calls).
- [ ] **AC-DATA-11** `food_group` is **non-nullable** client-side (§9 makes categories reliable) and no type cast bypasses it.
- [ ] **AC-DATA-12** DB-init failure surfaces to the user (§6) rather than being swallowed; the app does not proceed silently with an unusable database.

## C. Design system (§4)

- [ ] **AC-DS-01** Material widgets are used on both platforms; **no `cupertino` import** anywhere in `lib/`.
- [ ] **AC-DS-02** Brand tokens map onto `ColorScheme` + `TextTheme`, with exactly **one** `ThemeExtension` for what doesn't fit (tone pairs `warningLight`/`warning`, `ink`, `primaryLight`, radius/spacing/shadow scales).
- [ ] **AC-DS-03** **Token access is via `Theme.of(context)` only** — no global colour/typography const is imported at a call site in `lib/features/`.
- [ ] **AC-DS-04** Built-ins are themed centrally (`CardTheme`, `IconButtonTheme`, `SegmentedButtonTheme`, `SnackBarThemeData`, `*ButtonTheme`) rather than wrapped in bespoke widgets.
- [ ] **AC-DS-05** **The missing `Button` primitive exists**: themed `FilledButton`/`OutlinedButton`/`TextButton` plus a pill-chip variant. **No feature file hand-rolls a pill button** from a bare `GestureDetector`/`InkWell` + `Container` with its own radius/padding.
- [ ] **AC-DS-06** Icons come from built-in `Icons` `_rounded` variants; any exception is an individually-vendored SVG via `flutter_svg` with its Ionicons MIT provenance noted.
- [ ] **AC-DS-07** `GleanMark` renders from the vendored SVG via `flutter_svg`.
- [ ] **AC-DS-08** **Nothing named `AppText` exists** and no lint-guard script polices text imports (§4 — deleted, `TextTheme` replaces it). `fontWeight` resolves natively.
- [ ] **AC-DS-09** Swipe-to-delete uses built-in `Dismissible` — **no `PanResponder`-equivalent custom gesture/threshold code** and no `swipe_action` helper.
- [ ] **AC-DS-10** Snackbars use `ScaffoldMessenger`/`SnackBar` — no bespoke toast widget or queue.
- [ ] **AC-DS-11** Skeleton shimmer uses `TweenAnimationBuilder` — no manual `AnimationController.repeat()` shimmer loop.
- [ ] **AC-DS-12** `Badge` is the only bespoke primitive that remains (a tinted label pill), and it is justified in a comment.
- [ ] **AC-DS-13** Layout is **feature-first**: `lib/features/<feature>/{screen,widgets/,providers}`, `lib/design_system/`, `lib/router/`. No `lib/screens/` catch-all.
- [ ] **AC-DS-14** Sub-widgets are **extracted into their own classes with `const` constructors** — no screen file declares private sub-widget builders inline, and no screen file exceeds ~250 lines.

## D. Auth (§5)

- [ ] **AC-AUTH-01** Cognito Hosted UI → Google via `flutter_appauth` with PKCE; redirect is the custom scheme `glean://auth/callback`, matching `backend/template.yaml`.
- [ ] **AC-AUTH-02** Tokens live in `flutter_secure_storage`.
- [ ] **AC-AUTH-03** **Logout clears tokens explicitly** (iOS Keychain survives reinstall — reinstall-as-signout is not assumed).
- [ ] **AC-AUTH-04** **On token expiry local data stays readable** behind a "signed out" banner that gates only AI-backed features. The user is not routed away from their data.
- [ ] **AC-AUTH-05** Token refresh never writes a null/undefined access token while reporting a valid session (§11).
- [ ] **AC-AUTH-06** The bypass lives **only** in `main_e2e.dart`, plus a startup assertion that it is unreachable against a production API base URL.
- [ ] **AC-AUTH-07** A CI check asserts release builds use `main.dart` (§10.8) — a build-level guarantee, not a unit test.
- [ ] **AC-AUTH-08** iOS sign-in consumes `flutter_appauth`'s **returned** authorization result rather than depending on a deep link arriving (§11 — the RN bug).

## E. UX — cross-cutting (§6)

- [ ] **AC-UX-01** **Swipe-only deletes**: Pantry, Shop and Plan rows each expose exactly **one** delete affordance (the `Dismissible`), not two.
- [ ] **AC-UX-02** **Undo snackbar on every destructive action** — pantry item, shopping row, plan entry, recipe — with no confirm dialog.
- [ ] **AC-UX-03** **"Cooked" is undoable**: the pantry delta is stored and reversing it restores exact prior quantities.
- [ ] **AC-UX-04** A **short, skippable first-run setup** captures dinners/week, servings and dietary flags, ending by pointing at receipt-scan.
- [ ] **AC-UX-05** Settings copy states these values steer generation; the cooking-time field shows a **"minutes"** unit and surfaces its **1–480** bound *before* it is violated.

## F. UX — Pantry (§6)

- [ ] **AC-PAN-01** **Expiry is inferred automatically** from per-category shelf life and actually **written** to the row (the RN app never wrote one).
- [ ] **AC-PAN-02** Expiry drives badges, the "N expiring" chip and the Plan nudge from real stored data.
- [ ] **AC-PAN-03** **All three intake modes sit behind a `+` sheet** (Scan / Describe / Manual), reachable whether the pantry is **empty or full**.
- [ ] **AC-PAN-04** **Intake is a modal task**: the tab bar is hidden across scan → progress → review, with an explicit cancel. A stray tap cannot silently lose a capture.
- [ ] **AC-PAN-05** **One review screen** serves both pantry and shop intake — one look, one set of verbs, one numeric fallback rule.
- [ ] **AC-PAN-06** **Honest progress**: a real indeterminate indicator with timeout and cancel. **No artificial delay** and no fake staged steps.
- [ ] **AC-PAN-07** **Quantity editing is a sheet** covering quantity + unit + expiry with explicit Save/Cancel and real validation.
- [ ] **AC-PAN-08** **Decimal quantities are typeable** and non-numeric input cannot persist as NaN (§11).
- [ ] **AC-PAN-09** Zero/NaN quantities **fail** validation — Confirm cannot write `0 units` (§11).
- [ ] **AC-PAN-10** Review save is **atomic** — a mid-list failure persists nothing, and retrying cannot double quantities (§11).
- [ ] **AC-PAN-11** A pantry-only review **does not touch the shopping list** (§11).
- [ ] **AC-PAN-12** Deleting the last item of a filtered category **does not strand the list** — the filter resolves to a valid state (§11).
- [ ] **AC-PAN-13** Camera permission denied/pending states each have a **back affordance** — no dead end (§11).
- [ ] **AC-PAN-14** Capture and scan failures are **surfaced**, never silent; a scan failure cannot hang forever (timeout present) (§11).

## G. UX — Meals (§6)

- [ ] **AC-MEAL-01** Tapping a search result **previews** it; it is not silently saved.
- [ ] **AC-MEAL-02** The detail header bookmark is a **real save/unsave toggle** (not dead).
- [ ] **AC-MEAL-03** Saved recipes are **deletable**; deleting keeps any referencing plan entry (snapshot) and only drops the link.
- [ ] **AC-MEAL-04** **`not_suitable_for` is surfaced prominently** on the recipe detail.
- [ ] **AC-MEAL-05** **`source_url` is surfaced** as tappable attribution for imported recipes.
- [ ] **AC-MEAL-06** The detail header shows the **dish name**, not a static "Recipe".
- [ ] **AC-MEAL-07** **One search affordance** — a real inline input in the Search segment. No fake search pill, no separate pushed search screen.
- [ ] **AC-MEAL-08** After "Add to plan" the user **stays on the recipe**, sees a snackbar, and the button reflects "In plan".
- [ ] **AC-MEAL-09** Plan-full / already-planned is checked **before** navigating.
- [ ] **AC-MEAL-10** Search has real **empty** and **no-results** states; import **dedupes** and says "already saved".
- [ ] **AC-MEAL-11** Recipe detail uses skeletons (not a bare spinner) and its "to buy" badges cannot go stale (§11).
- [ ] **AC-MEAL-12** A cold-start deep link to a **missing recipe** shows an error with a working back affordance — never a permanent spinner (§11).
- [ ] **AC-MEAL-13** Recipe lookup by external id attaches dietary flags like its siblings (§11).

## H. UX — Shop (§6)

- [ ] **AC-SHOP-01** **Checkout stops deleting unmatched items** — only rows the receipt actually resolved are removed; the rest stay on the list.
- [ ] **AC-SHOP-02** An explicit **"Done shopping"** completes a receipt-less trip; checkout is not camera-only.
- [ ] **AC-SHOP-03** **Manual items resolve to an ingredient identity on entry** — `ingredient_id` is never null.
- [ ] **AC-SHOP-04** Check-off by ingredient is **scoped**: it never ticks rows outside the operation's scope or ones the user deliberately left unchecked.
- [ ] **AC-SHOP-05** Plan-derived shopping rows are **announced**, not silently inserted.
- [ ] **AC-SHOP-06** Deleting a planned meal **removes its shopping rows**.
- [ ] **AC-SHOP-07** Cart count wording is **unified** (one phrase, not "N checked" / "N items in cart" / "In your cart").
- [ ] **AC-SHOP-08** The add-item field is **pinned**, not a scrolling list header.
- [ ] **AC-SHOP-09** A DB error while adding an item **surfaces** and leaves the add button usable (§11 — never permanently disabled).
- [ ] **AC-SHOP-10** The checkout bar sits flush to the safe-area bottom — no ~90px dead band (§11).

## I. UX — Plan (§6)

- [ ] **AC-PLAN-01** The plan is **week-scoped** — queries filter on `planned_date`, which is now load-bearing.
- [ ] **AC-PLAN-02** **Week pagination** works forward and backward (last week's cooked meals are viewable today).
- [ ] **AC-PLAN-03** **Cooked meals stay visible** in their week but **stop counting** toward "left to plan".
- [ ] **AC-PLAN-04** **Capacity is per-week, not lifetime** — no permanent "Plan full" lockout.
- [ ] **AC-PLAN-05** **Uncooked meals roll forward** into the new week, and rollover is **idempotent** (repeat runs insert no duplicates).
- [ ] **AC-PLAN-06** Generation is **top-up only** — it fills empty slots and never replaces existing entries.
- [ ] **AC-PLAN-07** **`preferred_servings` is honoured** — plan entries no longer hardcode `servings: 1` (§6 dead feature).
- [ ] **AC-PLAN-08** **`food_groups` / `food_group_coverage` are populated**, so the backend's food-group balancing rule is live (§6 dead feature).
- [ ] **AC-PLAN-09** **Generate is disabled while pending** — a double-tap cannot overfill past capacity (§11).
- [ ] **AC-PLAN-10** Post-generation persistence is **guarded and atomic**: a bad `recipe_id` cannot half-write the plan silently; the user sees an error (§11).
- [ ] **AC-PLAN-11** **No re-add-on-focus bug**: navigating away from Plan and back cannot re-add a recipe (the `add_recipe_id` defect) — verified by a widget test.
- [ ] **AC-PLAN-12** The **progress ring animates** via `TweenAnimationBuilder` rather than teleporting.
- [ ] **AC-PLAN-13** The "Cooked?" pill → checkmark swap **transitions** rather than jumping.
- [ ] **AC-PLAN-14** Nav params are typed objects through `go_router` — **no `JSON.parse`-equivalent unguarded decode** can white-screen a route (§11).

## J. UX — Settings & auth (§6)

- [ ] **AC-SET-01** Settings **auto-save** on change, debounced, and on slider **release** — there is no Save button and no dirty-state trap.
- [ ] **AC-SET-02** Sliders do not write state every drag frame.
- [ ] **AC-SET-03** A config-save failure **surfaces** to the user (§11 — currently silent).
- [ ] **AC-SET-04** **Terms and Privacy are real tappable links.**
- [ ] **AC-SET-05** The landing tab is **Pantry**; sign-in is **Google-only**.

## K. Haptics & transitions (§7)

- [ ] **AC-HAP-01** The **three-weight ladder is implemented at design-system level**: `selectionClick` (tab/segment/chip/slider-step), `lightImpact` (default tappable ack), `mediumImpact` (data commit).
- [ ] **AC-HAP-02** `heavyImpact` and `vibrate` are **unused**.
- [ ] **AC-HAP-03** **No double-fire**: a single delete tap triggers exactly one haptic (the RN app buzzed twice).
- [ ] **AC-HAP-04** No feature file calls `HapticFeedback` directly — it goes through the design-system ladder, so screens cannot forget it.
- [ ] **AC-HAP-05** The previously-silent moments now fire: Google sign-in tap, sign-in success, sign-out, camera shutter, scan success/failure, both review confirms, **Generate tap and generation completion**, swipe-delete commit, filter-chip selection, every tab switch, slider steps.
- [ ] **AC-TRN-01** Skeleton → content **cross-fades** via `AnimatedSwitcher` everywhere; no hard cut and no bare spinner.
- [ ] **AC-TRN-02** List insert/remove is **animated**, and the gap a `Dismissible` leaves animates closed.
- [ ] **AC-TRN-03** Navigation uses **`push`/`pop` where the user is conceptually going back** — no `replace` that makes a back-navigation slide forward or leaves a stale screen in the stack.
- [ ] **AC-TRN-04** The expiry banner **fades** in/out rather than popping.
- [ ] **AC-TRN-05** Splash → app **fades**; there is exactly one splash composition and no unanimated hand-off.

## L. Backend change (§9) — the only sanctioned one

- [ ] **AC-BE-01** `POST /receipts/scan`, `POST /receipts/describe` and `POST /shopping/parse-description` each return a **`category`** per parsed ingredient.
- [ ] **AC-BE-02** Categories are drawn from the **existing 23-category taxonomy** — no new vocabulary introduced.
- [ ] **AC-BE-03** Backend tests cover the new field on all three endpoints, and the backend suite passes.
- [ ] **AC-BE-04** The Flutter client **persists** the returned category (it is not dropped on the way into the DB).
- [ ] **AC-BE-05** **No other backend behaviour changed** — the diff touches only what §9 sanctions.

## M. Testing (§10)

- [ ] **AC-TEST-01** A shared **`NativeDatabase.memory()`** fixture exists and is used by the data-layer tests — **one** fixture, not five copy-pasted harnesses.
- [ ] **AC-TEST-02** Data-layer tests assert **data outcomes**, not query-builder call shapes. No test asserts a "was this method called N times" expectation against the DB.
- [ ] **AC-TEST-03** Bucket counts are met: **28 unit**, **14 widget**, **1 integration** suite.
- [ ] **AC-TEST-04** The 7 dropped Jest files have **no Flutter counterpart**, and the 5 Maestro helpers are gone.
- [ ] **AC-TEST-05** The highest-value logic ports exist and pass: unit normalization (kg→g, L→ml, cup-of-flour→g by density), meal-plan compression (urgency scoring + top-N), meals/plan/settings presentation, shopping shortfall maths across servings, auth-mode logic.
- [ ] **AC-TEST-06** **New coverage 1 — checkout keeps unmatched items**: a receipt resolving 4 of 12 checked rows removes exactly those 4 and leaves 8.
- [ ] **AC-TEST-07** **New coverage 2 — user-scoped isolation**: user A's pantry/recipes/plan/shopping are invisible to user B on the same device.
- [ ] **AC-TEST-08** **New coverage 3 — undo** on every destructive action, including "Cooked" reversing its pantry delta.
- [ ] **AC-TEST-09** **New coverage 4 — week scoping, pagination, rollover idempotency, per-week capacity.**
- [ ] **AC-TEST-10** **New coverage 5 — expiry inference from category**, and that parsed ingredients **persist** their category.
- [ ] **AC-TEST-11** **New coverage 6 — preview-not-save** and recipe deletion.
- [ ] **AC-TEST-12** **New coverage 7 — settings auto-save.**
- [ ] **AC-TEST-13** **New coverage 9 — the haptic ladder** is asserted at design-system level.
- [ ] **AC-TEST-14** **New coverage 10 — `go_router` route-table structure** is asserted.
- [ ] **AC-TEST-15** The single `integration_test` suite covers the `smoke.yaml` intent: launch, five tabs visible, navigate each, add an item — including the manual-entry path that was dead code.
- [ ] **AC-TEST-16** Camera-permission handling folds into the integration suite.
- [ ] **AC-TEST-17** No test shims a navigation-focus callback to force a reload (§10 — that shim's reason is gone).
- [ ] **AC-TEST-18** The airplane-mode error-states flow is recorded as a **manual pre-release checklist item**, not automated.
- [ ] **AC-TEST-19** The redirect-URI cross-repo contract (`glean://auth/callback` present in `backend/template.yaml`) is checked.

## N. CI, release & cutover (§8)

- [ ] **AC-CI-01** A Linux CI job runs `flutter analyze` + `flutter test` (unit + widget) **on push**.
- [ ] **AC-CI-02** A `workflow_dispatch`-gated workflow holds **two separate jobs**: iOS integration on **macOS** (iOS Simulator) and Android integration on **Linux/KVM** (Android emulator). Neither runs on push.
- [ ] **AC-CI-03** Both integration jobs are documented as runnable **locally from one Mac**.
- [ ] **AC-CI-04** **Fastlane lanes** exist for iOS (TestFlight) and Android (Play internal), driven from the Mac, not wired into CI. **`match` is not used.**
- [ ] **AC-CI-05** **Build-number auto-increment has an explicit replacement** for what EAS was silently providing (§8) — documented and implemented.
- [ ] **AC-CI-06** `mobile/eas.json` and `.github/workflows/eas-build.yml` are **deleted**; no EAS reference remains anywhere.
- [ ] **AC-CUT-01** **`mobile/` is deleted.** No RN/Expo file, dependency, script or workflow remains; nothing in the repo references `mobile/`.
- [ ] **AC-CUT-02** `Makefile`, `README.md`, `AGENTS.md`/`CLAUDE.md` and `docs/` are updated for the Flutter app — every documented command works.
- [ ] **AC-CUT-03** Pre-commit config covers Dart formatting/analysis and drops the RN hooks.

## O. Final gates

- [ ] **AC-GATE-01** An independent verifier has confirmed **every** criterion above with evidence.
- [ ] **AC-GATE-02** A code reviewer has reviewed the full diff and has **no unresolved blocking finding**.
- [ ] **AC-GATE-03** No known bug from §11 is reproduced — each is either fixed by a criterion above or explicitly checked off in a §11 sweep.
