# Implementation Brief — Flutter Port

**Read this first, then your wave's task.** Every agent working this port shares these rules.

- **Spec (authoritative):** [`FLUTTER_MIGRATION.md`](../../FLUTTER_MIGRATION.md) at the repo root. It is *locked*. If you believe it is wrong, say so in your report — do not silently deviate.
- **Acceptance criteria:** [`ACCEPTANCE.md`](ACCEPTANCE.md). Your work is judged against specific `AC-*` ids. Your task names yours.
- **Decision provenance:** `issues/NN-*.md` if you need the reasoning or rejected alternatives behind a decision.

## Environment

```bash
export PATH="$HOME/.local/bin:$PATH"   # flutter 3.44.8 / dart 3.12.2 live here
cd /home/ruaridh/glean/.worktrees/flutter-port/app
```

- Working directory: `/home/ruaridh/glean/.worktrees/flutter-port` (a git worktree — **never `cd` to the main checkout**).
- The Flutter app is at **`app/`**.
- **No Android SDK, no Java, no Xcode, no emulator on this Linux box** — and none is needed. `flutter analyze`, `flutter test` (unit **and** widget) all run headless. `flutter build`/`flutter run`/`integration_test` cannot run here; that is expected and is a Mac concern per §8.
- `NativeDatabase.memory()` **works** headless (system libsqlite3 present). Verified.

### Verification commands (your work is not done until both are clean)

```bash
flutter analyze          # must print "No issues found!" — zero errors, warnings AND infos
flutter test             # must pass, nothing skipped
dart format --set-exit-if-changed lib test
dart run build_runner build --delete-conflicting-outputs   # only if you touched drift tables
```

`analysis_options.yaml` is strict on purpose (`prefer_const_constructors`, `require_trailing_commas`, `prefer_single_quotes`, `always_declare_return_types`, `unawaited_futures`, `avoid_print`). Do not weaken it, and do not sprinkle `// ignore:` to get green — fix the code.

## The reference app

`mobile/` is the Expo/React Native app being replaced. It is **read-only reference** — do not edit it. It is deleted in the cutover wave (AC-CUT-01), so port the *logic* you need out of it now.

Highest-value logic to port faithfully (behaviour, not structure):

| What | Where in `mobile/` |
|---|---|
| Unit normalization + densities | `src/normalization/units.ts` |
| Pantry compression / urgency scoring | `src/meal-plan/compress.ts` |
| Design tokens (colours, type scale, spacing, radii) | `src/theme/index.ts` |
| DB schema + queries | `src/db/` |
| API client + types | `src/api/` |
| Ingredient category taxonomy + staples seed | `src/db/ingredient-categories.ts`, `src/db/seed.ts` |
| Presentation helpers | `src/*/presentation.ts` |

**Port behaviour, not bugs.** §11 of the spec lists ~30 known defects in that app. Reproducing one is a failed criterion.

## House rules

1. **Screens never import drift or the API client** (AC-DATA-07). Everything goes through Riverpod providers. This is grepped for.
2. **No manual reload.** Reads are `StreamProvider` over drift `.watch()`. There is no on-focus refetch, no `loading` flag set on navigation, and **no `ref.invalidate` after a mutation** (AC-DATA-04/05). Mutations just write; streams re-emit.
3. **Tokens via `Theme.of(context)`** — never a global const at a call site (AC-DS-03). This is what keeps dark mode a second `ThemeData` instead of a codebase-wide refactor.
4. **Material only.** No `package:flutter/cupertino.dart` anywhere (AC-DS-01).
5. **Theme the built-in, don't wrap it.** Reach for `CardTheme`/`*ButtonTheme`/`SnackBarThemeData` before writing a bespoke widget. `Badge` is the one sanctioned bespoke primitive.
6. **Extract sub-widgets into their own classes with `const` constructors** (AC-DS-14) — in Flutter this is a rebuild-scope performance property, not just tidiness. No screen file over ~250 lines.
7. **Haptics only via the design-system ladder** (AC-HAP-04) — never call `HapticFeedback` from a feature file.
8. **Every user-data query is user-scoped** (AC-DATA-02/03). A missed scope is a data-leak criterion failure.
9. **Comment the non-obvious _why_,** matching the density of the surrounding code. Do not narrate the obvious.
10. **British English** in user-facing copy, matching the existing app.

## Module contract

Own only your directories. These are the seams between waves — code against them even before they exist.

| Module | Owns | Exports (import these, don't reinvent) |
|---|---|---|
| Data | `lib/data/**`, `test/data/**` | `GleanDatabase`, table/DAO classes, `lib/data/providers/*.dart` stream + mutation providers, `test/data/fixture.dart` in-memory fixture |
| Design system | `lib/design_system/**`, `test/design_system/**` | `gleanLightTheme` (`ThemeData`), `AppTokens` (`ThemeExtension`) + `context.tokens`, `Haptics` ladder, `GleanBadge`, `SkeletonBox`, `GleanMark` |
| Router | `lib/router/**`, `lib/app.dart`, `test/router/**` | `goRouterProvider`, route name/path constants, the tab shell |
| Features | `lib/features/<feature>/**`, `test/features/<feature>/**` | screens + their `widgets/` + their providers |
| API | `lib/api/**`, `test/api/**` | typed client + request/response models |
| Orchestrator only | `lib/main.dart`, `lib/main_e2e.dart`, `pubspec.yaml`, `analysis_options.yaml`, CI, Fastlane | — |

**Do not edit another module's files.** If you need something from one, and it is missing, define the smallest interface you need on your side of the seam and **flag it in your report** as a required follow-up. Parallel agents share this worktree, so an edit outside your directories can be silently clobbered.

## Reporting

Your final message is consumed by an orchestrator, not a human. Return:

1. **Files created/modified** (paths only).
2. **Per `AC-*` id you were assigned:** `DONE` / `PARTIAL` / `BLOCKED`, each with the `file:line` or command output that proves it. Be honest — an independent verifier re-checks every claim and a false `DONE` costs a whole extra loop iteration.
3. **`flutter analyze` and `flutter test` output** (the tail, verbatim).
4. **Seams you needed that didn't exist yet**, and what you stubbed.
5. **Anything in the spec that turned out wrong or under-specified.** This is valuable — surface it.
