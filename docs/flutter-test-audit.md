# Flutter round-two test audit

Reviewed baseline: `8931baa` (draft PR #102). Counts below refer to **runtime cases**, not files. This accounts for the independent review's 63 flagged original cases and three additional misleading cases; it is not a claim that every current test received a fresh body-level audit.

## Disposition of all 63 flagged cases

Original locations are relative to `app/test/`, unless prefixed with `backend/`. Grouped rows count each original case separately.

| Original case(s) | Count | Disposition and replacement/retained contract |
| --- | ---: | --- |
| Tokens ambient constants | 1 | Rewrite: rendered warning badge under alternate ambient tokens; golden fails if production ignores the override. |
| Tokens extension count | 1 | Delete: registry anatomy is not a UI outcome. |
| Theme typography/palette constants | 2 | Rewrite: rendered typography and actual primary/warning/error components. |
| Theme Cupertino substring scan | 1 | Delete: comments/file lists cannot prove platform rendering. |
| Filled/outlined/button-icon/chip styles | 4 | Rewrite: rendered goldens plus activation, toggling and accessible action labels. |
| Badge Container ancestry | 1 | Rewrite: readable, accessible status pills at 2x text scale. |
| Skeleton source scan | 1 | Delete; retain real shimmer/state-transition coverage. |
| List opacity/slide anatomy | 2 | Rewrite: visible insertion and preservation of existing rows through rendered frames. |
| Brand SVG/shadow anatomy | 2 | Rewrite: real vendored artwork rendered at app sizes, including visible stem/shadow. |
| Haptics recorder/source/default-constructor cases | 3 | Delete those three cases. Add one independent production-provider/platform-channel test; do not count a test recorder as production proof. |
| Progress painter fractions | 2 | Rewrite: rendered empty/count/progress frames and animation, without casting the painter. |
| Self-installed auth bypass wiring | 1 | Delete; retain the independent production import-graph/release guard. |
| Self-throwing auth override | 1 | Rewrite: production `sessionOverrides`, genuinely signed-out identity and assembled bootstrap wiring. |
| In-memory-only token storage contracts | 3 | Rewrite: actual `SecureTokenStorage` adapter at the secure-storage plugin boundary. |
| Standalone corpus null-ID decoder | 1 | Merge into corpus request/decode/persistence contract cases. |
| Obsolete saved-ID Generate fixtures | 2 | Rewrite as real Plan/router/SQLite flows using corpus external IDs/details, request settings, persisted meals/gaps and visible retry. |
| Obsolete controller double-tap case | 1 | Merge into corpus detail-pending single-flight coverage; add real manual/Generate overlap coverage. |
| Static route lists/prefixes | 3 | Merge into actual root/intake routed widget cases; retain unique-name validation because it is a router registration contract. |
| Never-pumped receipt-match checkout “widget” | 1 | Merge into real shopping repository outcomes; actual checkout UI rollback/retry is separately covered. |
| Throwing Plan repository subclasses | 3 | Rewrite with real SQLite failure triggers and user-visible error/recovery outcomes. All 12 Plan screen cases now use the real router/repositories rather than those subclasses. |
| Source-parsed taxonomy | 1 | Rewrite: frozen serialized backend wire fixture, actual Flutter decoder, actual seeded SQLite persistence. Backend serialization validates the same fixture. |
| Backend taxonomy-count constant | 1 | Delete; retain exact taxonomy equality and actual wire serialization. |
| Backend never-null food-group parametrization | 25 | Merge into 23 exact derivation outcomes plus null/invalid fallback outcomes. Exact strings already prove non-null receipt buckets; meal-plan food groups separately remain nullable. |
| **Total** | **63** | **8 deleted + 31 merged + 24 rewritten. Flutter 37; backend 26. No flagged case is silently retained.** |

Retained tests outside those deletions still cover legitimate contracts: HTTP wire shapes, production import/build guards, unique route names, exact taxonomy membership/derivation, real shimmer/crossfade transitions and real SQL persistence. They are not release/device proof.

Seventeen widget golden images were visually inspected. A controlled mutation making the production badge ignore ambient tokens failed the alternate-token golden; restoring the production implementation passed. This is headless rendering evidence only.

## Three misleading cases repaired separately

1. `data/shopping_repository_test.dart`: repeat of the **same meal** remains idempotent, while another meal retains its own requirement. Shared demand, display aggregation, deletion and cooking are checked with real SQLite.
2. `features/plan/plan_screen_test.dart`: Delete/Undo now checks restoration of shopping gaps and original entry ownership, not just the meal title. Cooked and deleted-recipe/title-only variants have separate real-route regressions.
3. Same file's re-focus case now **adds a recipe through the actual UI first**, navigates away/back and verifies exactly one persisted meal. An initially empty plan cannot prove this regression.

These three cases are not added to the 63 fluff count: **66 original cases accounted for**.

## All 22 requested behavioral gaps

Paths below omit the `app/test/` prefix. “Covered” means executable headless behavior at the named public seam, not native acceptance.

| # | Outcome | Evidence |
| ---: | --- | --- |
| 1 | Covered: corpus Generate honors request settings/exclusions and persists recipes, servings, meals and shopping demand; announces shopping additions. | `features/plan/generate_week_controller_test.dart`, `corpus_generation_test.dart` |
| 2 | Covered: manual double-tap overlapping pending Generate cannot duplicate or exceed fresh capacity. | `features/plan/corpus_edge_contract_test.dart` |
| 3 | Covered: changed dinners/week limit governs persistence. | `regression/review_regressions_test.dart` |
| 4 | Covered: all detail fetches failing leaves no half-plan, shows retry, and subsequent retry succeeds. | `features/plan/generate_week_controller_test.dart` |
| 5 | Covered: deleted library recipe retains corpus exclusion identity. | `regression/review_regressions_test.dart` |
| 6 | Covered: numeric, missing and blank corpus identities fail/skip recoverably with no half-write and a successful retry. | `features/plan/corpus_edge_contract_test.dart` (3 runtime variants) |
| 7 | Covered: mid-batch detail persistence failure leaves no plan/gaps; retry reuses already saved details safely. | Same file, real SQL trigger |
| 8 | Covered: warm Monday/resume rollover runs once; full-week rollover is oldest-first and preserves excess. | `features/plan/week_boundary_test.dart` |
| 9 | Covered: actual manual Add targets the viewed week and explicit planned date. | `regression/review_regressions_test.dart` |
| 10 | Covered: complete meal deletion Undo, with gaps, original IDs, cooked deltas and deleted-recipe/title-only state; recipe Undo restores surviving plan links. | Same file and `features/plan/plan_screen_test.dart` |
| 11 | Covered: undo cooking restores recipe history without clobbering a later cook. | `regression/review_regressions_test.dart` |
| 12 | Covered: compatible quantities normalize into a real shortfall. | Same file, e.g. 0.3kg requirement with 200g stock → 100g gap |
| 13 | Covered: shared stock allocated once; deleting/cooking either meal preserves remaining demand, including density-compatible mass/volume requirements and unit edits. | Same file and `data/shopping_repository_test.dart`; base-unit density regressions in `data/unit_normalization_test.dart` |
| 14 | Covered: unconvertible cooking units reject without consuming stock. | `regression/review_regressions_test.dart` |
| 15 | Covered: receipt checkout deletion failure rolls back stock/cart; user dismisses feedback and retries without doubling stock. | Same file, actual Review UI + SQL trigger |
| 16 | Covered: multiple answer rounds retain edited units/quantities, removals and selection through final save. | `features/intake/shopping_answers_test.dart` |
| 17 | Covered: expired/identity-only restart through assembled `GleanRoot` keeps local data readable and AI gated. | `auth/restart_access_test.dart`, production storage/factory seam |
| 18 | Covered: refresh/logout, concurrent refresh and already-started storage save/logout/failed-login races cannot restore/overwrite the session. | `auth/session_races_test.dart` |
| 19 | **Partial / native-release blocked:** both real lane definitions validate/pass production config, use the production entrypoint/artifact paths, and increment above all tracks. Eight executable Ruby fake-boundary cases plus existing import/release guards pass. No actual release artifact smoke or signed lane has run. | `app/scripts/test_release_lanes.rb`; `build/release_entrypoint_test.dart`; `auth/auth_bypass_test.dart` |
| 20 | Covered: real connectivity-channel transitions and HTTP 403 show offline/auth recovery while local data remains usable. Automatic remote-query retries no longer hide failures indefinitely behind loading skeletons. | `router/offline_banner_test.dart`, `auth_rejection_recovery_test.dart` |
| 21 | Covered: frozen Flutter-v1 file database reopens/upgrades without losing user data, duplicating seeds or losing FK behavior; legacy gaps and corpus identity survive. | `data/database_reopen_test.dart`, `data/fixtures/schema_v1.sql` |
| 22 | Covered: 403/429/non-JSON 502 map correctly; stalled scan token acquisition times out and late completion cannot dispatch the abandoned scan. | `api/recovery_contract_test.dart` (4 runtime cases) |

**Accounting:** 21 behavior gaps covered; one partially covered pending actual native/release artifact evidence. Real Cognito, camera, secure-storage and haptics plugin behavior remain separate native gates. Live AI remains unavailable; Android SDK installation and release/signing/store operations were not performed.
