# Flutter Port Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the Flutter app at `app/` from ~16.5k hand-written Dart lines in 163 files to roughly 11k lines in ~100 files by deleting one-adapter seams, pass-through layers, hand-rolled widgets, config-grepping tests and process-citation comments, while making the repo's coding standards first-class and machine-enforced.

**Architecture:** The drift → `StreamProvider` → `AsyncValue` core, go_router shell, Material theming, repositories, snapshot-exact Undo, user scoping and migration tests all stay. What goes is indirection *around* that core: `AsyncNotifier` command wrappers over single API calls, abstract classes with one production adapter, duplicated query/undo shapes, and tests that assert source text or config instead of behaviour. A new `test/standards/house_rules_test.dart` encodes the standards as a ratchet so they cannot regress.

**Tech Stack:** Flutter 3.44 / Dart 3.12, `flutter_riverpod` 3, `drift` 2, `go_router` 17, `flutter_appauth`, `flutter_secure_storage`, `mocktail`, `json_serializable` (Task 13 only).

**Spec:** The review that produced this plan is summarised in this file's "Review findings" section. Behavioural requirements remain those of `FLUTTER_MIGRATION.md`, including its 2026-10-06 and 2026-10-07 decision blocks, which are **not** relaxed by this plan.

## Global Constraints

- Work only in the worktree `/home/ruaridh/glean/.worktrees/flutter-simplify` on branch `refactor/flutter-simplify`. Never `cd` into `.worktrees/flutter-rebase` (another session owns it).
- `flutter analyze` must report **0 issues** and `dart format --output=none --set-exit-if-changed lib test integration_test` must pass before every commit. Run both from `app/`.
- `memcap flutter test` (from `app/`) must pass before every commit. Baseline at plan time: see "Baseline" below.
- Never relax, delete or skip: user-scoped tables, snapshot-exact Undo (`deletion_snapshots.dart`, `deleteWithSnapshot`, `restoreDeleted`, `restoreRows`, `undoCooked`), `database_reopen_test.dart` + `schema_v1.sql`, `session_races_test.dart`'s logout-wins behaviour, `user_isolation_test.dart`, `review_regressions_test.dart`, the `main.dart`/`main_e2e.dart` entrypoint split, `assertAuthBypassUnreachable`, `connectivity_plus` offline banner. These are 2026-10-07 spec decisions the user chose to keep.
- Commit after every task with a gitmoji subject and a one-line body stating *why*. Example: `♻️ refactor(app): delete API command controllers` / body `Each wrapped one client call behind an AsyncNotifier plus a keepAlive workaround for a bug the wrapper itself caused.`
- Do not touch `backend/`, `infra/`, or `FLUTTER_MIGRATION.md` except where a task says so.
- Prefer a library or Flutter built-in over hand-rolled code wherever one does the job (user preference).
- Comments: keep only comments that state a *current* constraint or non-obvious reason for the code as it now is. Delete any comment that cites `AC-xxx-nn`, `R-nn`, `F-nn`, `FINDINGS.md`, `REMEDIATION.md`, `.scratch/`, "Wave n", "orchestrator", or narrates what the React Native app used to do.

## Baseline

Before Task 1, record the baseline in the scratchpad (not committed):

```bash
cd /home/ruaridh/glean/.worktrees/flutter-simplify/app
find lib -name '*.dart' -not -name '*.g.dart' | xargs cat | wc -l      # 16534 at plan time
find lib -name '*.dart' -not -name '*.g.dart' | wc -l                  # 162
find test integration_test -name '*.dart' | xargs cat | wc -l          # ~14800
memcap flutter test --reporter compact 2>&1 | tail -3
```

## Review Focus

Inputs the spec implies but no existing test exercises, most likely to bite first. Each is pinned to the task that owns the code.

1. **A screen that fires an API call then is popped before the response arrives** must not throw or write to a disposed widget. Task 3 adds a `mounted` check test to `scan_progress_screen_test.dart`.
2. **Undo tapped after the originating route has been popped** must still restore and must report failure via the captured messenger, not a dead context. Task 4's `runUndoable` test covers pop-then-undo.
3. **A `features/` file importing drift row types or `database.dart`** must fail CI, not just a doc rule. Task 1's ratchet test, Task 4 removes the last allowlisted entries.
4. **A raw `Colors.*` or `Color(0x…)` in a feature widget** must fail CI once Task 5 lands; Task 1's ratchet test, emptied by Task 5.
5. **Cold start with secure storage holding a `userSub` but no access token** must land the app in `expired` with local data readable. Task 10 keeps and adapts `restart_access_test.dart` for the new constructor; run it explicitly.

## Review findings this plan implements

From the three-axis review of `flutter/rebase-on-main` on 2026-10-08, filtered by the user's annotations:

- **Delete the command-controller cruft** (4 `AsyncNotifier` wrappers + `command_provider_keep_alive_test.dart`).
- **Prefer libraries/built-ins over hand-rolled code** (`GleanCrossFade`, `GleanListEntrance`, 5 skeleton files, hand `fromJson`, hand multipart body).
- **Keep** snapshot Undo, user scoping, migration tests, logout-wins races (spec 2026-10-07 decisions).
- **Make the standards first-class** in `app/AGENTS.md` and enforce them in a test.
- **Fix the 4 hard violations** (house rule broken + unenforced; raw colours/paddings; hand-rolled test mocks; committed golden-diff artefacts and `.scratch` citations) **and the judgement smells** (Middle Man, Duplicated Code, Speculative Generality, dead code, Primitive Obsession, comment bloat).

---

### Task 1: First-class standards + ratchet test

**Files:**
- Modify: `app/AGENTS.md` (replace the "Architecture" and "Testing" sections)
- Create: `app/test/standards/house_rules_test.dart`
- Move: `app/test/auth/auth_bypass_test.dart` import-graph case → into the new file (keep the other two groups in place)

**Interfaces:**
- Produces: `house_rules_test.dart` with three allowlists (`_featureDataImportAllowlist`, `_rawColourAllowlist`, `_citationAllowlist`). Later tasks delete entries; Task 11 asserts all three are empty and deletes them.

- [ ] **Step 1: Rewrite the standards section of `app/AGENTS.md`**

Replace everything from `## Architecture` to the end of the file with:

````markdown
## Architecture

Feature-first Flutter app: `go_router` + `flutter_riverpod` + `drift`
(SQLite). All user state lives on-device; the FastAPI backend (`../backend/`)
is a stateless AI processing service. `FLUTTER_MIGRATION.md` at the repo root
is the behavioural spec.

```
lib/
├── main.dart                # Production entrypoint — never reaches auth_bypass.dart
├── main_e2e.dart             # integration_test entrypoint — the ONLY importer of auth_bypass.dart
├── bootstrap.dart            # Shared startup wiring both entrypoints call into
├── app.dart                  # MaterialApp.router root widget
├── data/                     # drift tables, repositories, providers.dart (Stream providers)
├── design_system/            # ThemeData, AppTokens (ThemeExtension), Haptics, GleanSnackBar, ListSkeleton
├── router/                   # go_router table, route constants, the five-tab shell
├── api/                      # Typed HTTP client + models + api_providers.dart
└── features/<feature>/       # Screen + widgets/ + providers, one dir per tab/flow
test/                          # Unit + widget tests mirroring lib/, plus test/standards/
integration_test/              # The one integration_test suite (app_test.dart), against main_e2e.dart
```

## Standards

Enforced by `test/standards/house_rules_test.dart`; `flutter analyze` and
`dart format` cover the rest. Do not add allowlist entries to that test to get
a change through.

1. **Data access only through providers.** Nothing under `lib/features/**`
   imports `package:drift`, `lib/data/database.dart`, `lib/data/tables.dart`
   or `lib/data/deletion_snapshots.dart`, and nothing constructs a repository
   or `GleanApiClient`. Read them with `ref.read(xRepositoryProvider)` /
   `ref.read(apiClientProvider)`. Importing a repository file for an
   exception type is fine.
2. **Colours and spacing come from the theme.** Outside `lib/design_system/`
   there is no `Colors.*` (except `Colors.transparent`) and no `Color(0x…)`.
   Use `Theme.of(context).colorScheme` and `context.tokens`. Camera-overlay
   colours are tokens too (`tokens.color.onCamera`, `cameraScrim`,
   `cameraBackdrop`).
3. **No process citations in code.** Comments explain the current
   constraint, not the ticket that introduced it: no `AC-…`, `R-nn`, `F-nn`,
   `FINDINGS.md`, `REMEDIATION.md`, `.scratch/`, "Wave", "orchestrator", or
   React Native history.
4. **Delete rather than wrap.** No abstract class with a single production
   implementation unless the real dependency cannot run under `flutter test`
   (today: `Haptics`, `ReceiptCameraController`). Use mocktail on the
   concrete class instead.
5. **Mutations just write.** Reads are drift `.watch()` streams; there is no
   `ref.invalidate` after a mutation and no manual reload on focus.
6. **One API call needs no controller.** Screens call
   `ref.read(apiClientProvider)` and hold their own pending flag.
7. **Destructive actions go through `GleanSnackBar.runUndoable`.** It owns
   the try/catch, undo snackbar and failure messages.

## Testing

- One in-memory drift fixture (`test/data/fixture.dart`) and one widget harness
  (`test/support/harness.dart`) that pumps a real `GoRouter` + real database.
  Use them; do not hand-roll fake repositories or databases. To make a
  repository fail, use a SQLite trigger on the fixture (see
  `shop_screen_test.dart`).
- Tests assert behaviour through the widget or repository seam. No test reads
  files under `lib/` or scans YAML/Fastfiles/PNGs except
  `test/standards/house_rules_test.dart`.
- No golden images.
- `RecordingHaptics` in the harness asserts the haptic ladder.

## Auth bypass

`lib/main_e2e.dart` is the only file besides `lib/auth/auth_bypass.dart`
allowed to import it; `test/standards/house_rules_test.dart` enforces this.
Never loosen it.
````

- [ ] **Step 2: Write the ratchet test**

Create `app/test/standards/house_rules_test.dart`:

```dart
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// Repo standards from `app/AGENTS.md` §Standards, enforced as a ratchet:
/// each allowlist names files that violated the rule when the rule was
/// introduced. Entries may only ever be removed.
const Set<String> _featureDataImportAllowlist = <String>{
  'lib/features/shop/actions.dart',
  'lib/features/plan/actions.dart',
  'lib/features/meals/actions.dart',
};

const Set<String> _rawColourAllowlist = <String>{
  'lib/bootstrap.dart',
  'lib/features/shop/widgets/shop_add_field.dart',
  'lib/features/shop/widgets/shopping_row.dart',
  'lib/features/shop/widgets/shop_checkout_bar.dart',
  'lib/features/meals/meals_import_screen.dart',
  'lib/features/auth/sign_in_screen.dart',
  'lib/features/intake/scan_screen.dart',
  'lib/features/intake/widgets/scan_back_button.dart',
  'lib/features/intake/widgets/camera_permission_prompt.dart',
  'lib/features/intake/widgets/scan_overlay.dart',
};

/// Populated from `rg -l` at introduction time — see Step 3.
const Set<String> _citationAllowlist = <String>{
  // FILLED IN STEP 3
};

final RegExp _forbiddenFeatureImport = RegExp(
  r'''^\s*import\s+['"](package:drift/|package:glean/data/(database|tables|deletion_snapshots)\.dart|\.\./.*data/(database|tables|deletion_snapshots)\.dart)''',
  multiLine: true,
);

final RegExp _rawColour = RegExp(
  r'\bColors\.(?!transparent\b)\w+|\bColor\(0x[0-9A-Fa-f]{8}\)',
);

final RegExp _citation = RegExp(
  r'AC-[A-Z]+-\d+|\bR-\d\d\b|\bF-\d\d\b|FINDINGS\.md|REMEDIATION\.md|\.scratch/|\bWave \d|orchestrator',
);

final RegExp _bypassImport = RegExp(
  r'''^\s*(import|export)\s+['"][^'"]*auth_bypass\.dart['"]''',
  multiLine: true,
);

Iterable<File> _dartFiles(String root) => Directory(root)
    .listSync(recursive: true)
    .whereType<File>()
    .where((f) => f.path.endsWith('.dart') && !f.path.endsWith('.g.dart'));

String _rel(File f) => f.path.replaceAll('\\', '/');

void _expectRatchet({
  required Iterable<File> files,
  required bool Function(String source) violates,
  required Set<String> allowlist,
  required String rule,
}) {
  final violations = <String>[];
  final stillNeeded = <String>{};
  for (final file in files) {
    final path = _rel(file);
    if (!violates(file.readAsStringSync())) continue;
    if (allowlist.contains(path)) {
      stillNeeded.add(path);
    } else {
      violations.add(path);
    }
  }
  expect(violations, isEmpty, reason: '$rule — see app/AGENTS.md §Standards');
  expect(
    allowlist.difference(stillNeeded),
    isEmpty,
    reason: 'Allowlist entries that no longer violate must be removed: ',
  );
}

void main() {
  test('features reach data only through providers (rule 1)', () {
    _expectRatchet(
      files: _dartFiles('lib/features'),
      violates: _forbiddenFeatureImport.hasMatch,
      allowlist: _featureDataImportAllowlist,
      rule: 'lib/features/** must not import drift, database.dart, '
          'tables.dart or deletion_snapshots.dart',
    );
  });

  test('colours come from the theme outside design_system (rule 2)', () {
    _expectRatchet(
      files: _dartFiles('lib').where(
        (f) => !_rel(f).startsWith('lib/design_system/'),
      ),
      violates: _rawColour.hasMatch,
      allowlist: _rawColourAllowlist,
      rule: 'no Colors.* (except transparent) or Color(0x…) outside '
          'lib/design_system/',
    );
  });

  test('no process citations in comments (rule 3)', () {
    _expectRatchet(
      files: _dartFiles('lib'),
      violates: _citation.hasMatch,
      allowlist: _citationAllowlist,
      rule: 'no AC-/R-/F-/FINDINGS/REMEDIATION/.scratch/Wave/orchestrator '
          'references in lib/',
    );
  });

  test('only main_e2e.dart imports auth_bypass.dart', () {
    const allowed = <String>{'lib/auth/auth_bypass.dart', 'lib/main_e2e.dart'};
    final violations = <String>[
      for (final f in _dartFiles('lib'))
        if (!allowed.contains(_rel(f)) && _bypassImport.hasMatch(f.readAsStringSync()))
          _rel(f),
    ];
    expect(violations, isEmpty,
        reason: 'These files would pull the test bypass into a release build');
  });
}
```

- [ ] **Step 3: Fill the citation allowlist from the current tree**

```bash
cd /home/ruaridh/glean/.worktrees/flutter-simplify/app
rg -l 'AC-[A-Z]+-\d+|\bR-\d\d\b|\bF-\d\d\b|FINDINGS\.md|REMEDIATION\.md|\.scratch/|\bWave \d|orchestrator' lib -g '!*.g.dart' | sort | sed "s|.*|  '&',|"
```

Paste the output into `_citationAllowlist`. Expect roughly 128 entries.

- [ ] **Step 4: Remove the import-graph case from `test/auth/auth_bypass_test.dart`**

Delete the final `test('AC-AUTH-06: no file under lib/ …')` block and the now-unused `import 'dart:io';`. Keep the `bypassAuthSnapshot` and `assertAuthBypassUnreachable` groups.

- [ ] **Step 5: Run the new test and the suite**

```bash
flutter test test/standards/house_rules_test.dart test/auth/auth_bypass_test.dart
```
Expected: PASS (the allowlists exactly cover today's violations). If a rule 1 or 2 violation appears that is not listed above, add it to the allowlist in this task only, and note it in the commit body.

```bash
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
```

- [ ] **Step 6: Commit**

```bash
git add app/AGENTS.md app/test/standards/house_rules_test.dart app/test/auth/auth_bypass_test.dart
git commit -m "📏 standards(app): make the house rules first-class and machine-enforced" -m "The providers-only rule was documented as grepped-for but nothing grepped; a ratchet test lets later tasks remove violations without a flag day."
```

---

### Task 2: Delete config-grepping tests, goldens and the Fastlane stub harness

**Files:**
- Delete: `app/test/build/release_entrypoint_test.dart`, `app/test/build/launcher_brand_test.dart`, `app/test/build/network_permissions_test.dart`, `app/test/auth/redirect_uri_contract_test.dart`, `app/test/support/visual.dart`, `app/test/design_system/goldens/` (whole dir), `app/test/design_system/failures/` (whole dir), `app/scripts/test_release_lanes.rb`, `app/scripts/generate_launcher_icons.py` (if nothing in `fastlane/` or `Makefile` invokes it — check with `rg generate_launcher_icons ..`).
- Modify: the 7 tests that import `support/visual.dart` (`test/features/plan/plan_progress_card_test.dart`, `test/design_system/{buttons,brand_mark,badge,tokens,list_entrance,theme}_test.dart`): remove every `matchesGoldenFile`/`expectVisual` assertion and the import; keep the behavioural assertions. If a test has nothing left, delete the file. (`list_entrance_test.dart` is deleted in Task 6 regardless.)
- Modify: `app/pubspec.yaml` — remove `xml` from dev_dependencies if `rg "package:xml" test lib` is empty after the deletions.
- Modify: `.github/workflows/flutter-ci.yml` — remove the step that runs `scripts/test_release_lanes.rb`. Add, in the Linux lint/unit job, one step that keeps the spec's "release builds use main.dart" guarantee without a 349-line test:

```yaml
      - name: Release lanes never target main_e2e.dart
        run: |
          ! grep -rn 'main_e2e' app/fastlane .github/workflows --include='*' \
            | grep -v 'flutter-ci.yml' | grep -v -i 'integration\|e2e-job' \
            || { echo 'A release path references main_e2e.dart'; exit 1; }
```
  Read the workflow first and adjust the grep's exclusions so the e2e job's own legitimate reference does not trip it. Also fix the comment at line ~7 that says "neither runs on push" if it contradicts the `on:` block.
- Modify: `app/README.md` — delete any paragraph describing the deleted scripts or golden workflow.

- [ ] **Step 1: Delete the files**

```bash
cd /home/ruaridh/glean/.worktrees/flutter-simplify/app
git rm -r test/build test/auth/redirect_uri_contract_test.dart test/support/visual.dart test/design_system/goldens test/design_system/failures scripts/test_release_lanes.rb
rg -n generate_launcher_icons .. --glob '!**/.worktrees/**' && echo KEEP || git rm scripts/generate_launcher_icons.py
```

- [ ] **Step 2: Strip golden assertions from the seven tests**

For each file in the list, remove `import '../support/visual.dart';` (path varies) and every statement that calls a helper from it. Run `flutter test <file>` after each edit; delete the file if it has no `test(`/`testWidgets(` left.

- [ ] **Step 3: Edit the CI workflow and pubspec**

Apply the YAML change above. Then:

```bash
rg -n 'package:xml' lib test || sed -i '/^  xml: /d' pubspec.yaml
flutter pub get
```

- [ ] **Step 4: Verify**

```bash
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git status --short   # no stray PNGs
```

- [ ] **Step 5: Commit**

```bash
git add -A app .github/workflows/flutter-ci.yml
git commit -m "🔥 test(app): drop config-grepping tests, goldens and the Fastlane stub harness" -m "They asserted YAML, PNG pixels and manifest text rather than behaviour, and the spec had already dropped the CI-YAML regex test they re-created."
```

---

### Task 3: Delete the API command controllers

**Files:**
- Delete: `app/lib/api/providers/receipts_providers.dart`, `app/lib/api/providers/meal_plan_providers.dart`, `app/lib/api/providers/shopping_providers.dart`, `app/test/api/providers/command_provider_keep_alive_test.dart`
- Modify: `app/lib/api/providers/recipe_providers.dart` (remove `ImportRecipeController` + its provider; keep `recipeSearchProvider`, `recipeDetailProvider`)
- Modify: `app/lib/api/api.dart` (barrel — drop the deleted exports)
- Modify callers: `app/lib/features/intake/scan_progress_screen.dart`, `app/lib/features/intake/pantry_describe_screen.dart`, `app/lib/features/intake/shop_describe_screen.dart`, `app/lib/features/intake/review_screen.dart` (re-parse on clarification answers), `app/lib/features/meals/meals_import_screen.dart`, `app/lib/features/plan/providers/generate_week_controller.dart`
- Tests: `app/test/features/intake/scan_progress_screen_test.dart` (add the pop-before-response case), others should pass unchanged because they mock `httpClientProvider`.

**Interfaces:**
- Consumes: `GleanApiClient.scanReceipt(Uint8List, {String filename})`, `.describeReceipt(String)`, `.parseShoppingDescription(String)`, `.importRecipeFromUrl(ImportUrlRequest)`, `.generateMealPlan(MealPlanRequest)` via `ref.read(apiClientProvider)`.
- Produces: nothing new. The pattern every caller now uses:

```dart
// inside a ConsumerStatefulWidget's State
bool _pending = false;

Future<void> _submit() async {
  if (_pending) return;
  setState(() => _pending = true);
  try {
    final response = await ref.read(apiClientProvider).describeReceipt(text);
    if (!mounted) return;
    context.push(AppRoutes.intakeReview.path, extra: toReviewArgs(response));
  } on ApiException catch (error) {
    if (!mounted) return;
    GleanSnackBar.show(context, error.userMessage);
  } finally {
    if (mounted) setState(() => _pending = false);
  }
}
```

- [ ] **Step 1: Read each caller and note what it does on loading / data / error**

Each currently uses `ref.listen<AsyncValue<X?>>(controllerProvider, …)` for navigation and `ref.watch(controllerProvider).isLoading` for the button state. Preserve exactly those behaviours (navigation target, snackbar text, button disabled while pending, back button availability) with the local-state pattern above. For `review_screen.dart`, the re-parse keeps the edited values and selections — read `shopping_answers_test.dart` first; that test must keep passing.

- [ ] **Step 2: Add the failing pop-before-response test**

Append to `app/test/features/intake/scan_progress_screen_test.dart` (adapt the harness/mocked-client setup already used in that file):

```dart
testWidgets('popping during an in-flight scan neither throws nor navigates', (tester) async {
  final completer = Completer<http.Response>();
  // arrange: mocked http client whose send() returns completer.future
  // (reuse the file's existing mock wiring)
  await harness.pumpRoute(tester, AppRoutes.intakeScanProgress.path,
      extra: ScanProgressArgs(photoBytes: Uint8List(4)));
  harness.router.pop();
  await tester.pump();
  completer.complete(http.Response('{"items":[]}', 200));
  await tester.pumpAndSettle();
  expect(tester.takeException(), isNull);
  expect(harness.router.state.uri.path, isNot(AppRoutes.intakeReview.path));
});
```

Run: `flutter test test/features/intake/scan_progress_screen_test.dart` — expected to FAIL to compile until Step 3 (the controller provider is gone) or to pass trivially; either way it must pass after Step 3.

- [ ] **Step 3: Rewrite the callers and delete the controllers**

Delete the three provider files and `ImportRecipeController`. In `generate_week_controller.dart` replace

```dart
final command = ref.read(generateMealPlanControllerProvider.notifier);
await command.generate(request);
final result = command.state;
if (result.hasError) { Error.throwWithStackTrace(result.error!, result.stackTrace!); }
… result.value?.suggestions …
```
with
```dart
final MealPlanResponse response = await ref.read(apiClientProvider).generateMealPlan(request);
… response.suggestions …
```

Update `lib/api/api.dart` exports. Delete `test/api/providers/command_provider_keep_alive_test.dart`.

- [ ] **Step 4: Verify**

```bash
rg -n 'ControllerProvider|keepAlive\(' lib   # expect only generateWeekControllerProvider hits
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add -A app
git commit -m "♻️ refactor(app): call the API client directly instead of through command controllers" -m "Each AsyncNotifier wrapped one client call and carried a keepAlive workaround for a disposal bug the wrapper itself introduced."
```

---

### Task 4: One `runUndoable` helper; collapse the four `actions.dart`

**Files:**
- Modify: `app/lib/design_system/snackbar.dart` (add `runUndoable`)
- Modify: `app/lib/features/shop/actions.dart`, `app/lib/features/plan/actions.dart`, `app/lib/features/pantry/actions.dart`, `app/lib/features/meals/actions.dart`
- Create: `app/test/design_system/run_undoable_test.dart`
- Modify: `app/test/standards/house_rules_test.dart` — empty `_featureDataImportAllowlist`.

**Interfaces:**
- Produces:

```dart
/// Runs a destructive [perform], shows the undo snackbar, and runs [undo]
/// with perform's result if tapped. All failures surface as snackbars on the
/// messenger captured *before* perform, so a popped route cannot swallow them.
/// Returns true when perform succeeded.
static Future<bool> runUndoable<T>(
  BuildContext context, {
  required Future<T> Function() perform,
  required Future<void> Function(T snapshot) undo,
  required String message,
  required String failureMessage,
  required String undoFailureMessage,
  String Function(Object error)? describeError,
  VoidCallback? onSuccess,
})
```

- [ ] **Step 1: Write the failing test**

Create `app/test/design_system/run_undoable_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';

Future<BuildContext> _pumpHost(WidgetTester tester) async {
  late BuildContext captured;
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: Builder(builder: (context) {
      captured = context;
      return const SizedBox();
    })),
  ));
  return captured;
}

void main() {
  testWidgets('shows undo and restores from the snapshot', (tester) async {
    final context = await _pumpHost(tester);
    String? restored;
    final ok = await GleanSnackBar.runUndoable<String>(
      context,
      perform: () async => 'snap',
      undo: (s) async => restored = s,
      message: 'Removed',
      failureMessage: 'Could not remove',
      undoFailureMessage: 'Could not restore',
    );
    await tester.pump();
    expect(ok, isTrue);
    expect(find.text('Removed'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pump();
    expect(restored, 'snap');
  });

  testWidgets('a failing perform shows failureMessage and returns false', (tester) async {
    final context = await _pumpHost(tester);
    final ok = await GleanSnackBar.runUndoable<void>(
      context,
      perform: () async => throw StateError('db'),
      undo: (_) async {},
      message: 'Removed',
      failureMessage: 'Could not remove',
      undoFailureMessage: 'Could not restore',
    );
    await tester.pump();
    expect(ok, isFalse);
    expect(find.text('Could not remove'), findsOneWidget);
  });

  testWidgets('describeError overrides failureMessage', (tester) async {
    final context = await _pumpHost(tester);
    await GleanSnackBar.runUndoable<void>(
      context,
      perform: () async => throw const FormatException('units'),
      undo: (_) async {},
      message: 'x', failureMessage: 'generic', undoFailureMessage: 'y',
      describeError: (e) => e is FormatException ? 'Unit mismatch' : 'generic',
    );
    await tester.pump();
    expect(find.text('Unit mismatch'), findsOneWidget);
  });

  testWidgets('a failing undo reports on the captured messenger', (tester) async {
    final context = await _pumpHost(tester);
    await GleanSnackBar.runUndoable<void>(
      context,
      perform: () async {},
      undo: (_) async => throw StateError('db'),
      message: 'Removed', failureMessage: 'f', undoFailureMessage: 'Could not restore',
    );
    await tester.pump();
    await tester.tap(find.text('Undo'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    expect(find.text('Could not restore'), findsOneWidget);
  });
}
```

Run: `flutter test test/design_system/run_undoable_test.dart` → FAIL (`runUndoable` undefined).

- [ ] **Step 2: Implement `runUndoable` in `snackbar.dart`**

```dart
static Future<bool> runUndoable<T>(
  BuildContext context, {
  required Future<T> Function() perform,
  required Future<void> Function(T snapshot) undo,
  required String message,
  required String failureMessage,
  required String undoFailureMessage,
  String Function(Object error)? describeError,
  VoidCallback? onSuccess,
}) async {
  final messenger = ScaffoldMessenger.of(context);
  final T snapshot;
  try {
    snapshot = await perform();
  } catch (error) {
    if (messenger.mounted) {
      showOn(messenger, describeError?.call(error) ?? failureMessage);
    }
    return false;
  }
  onSuccess?.call();
  if (!messenger.mounted) return true;
  messenger
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(
      content: Text(message),
      action: SnackBarAction(
        label: 'Undo',
        onPressed: () => unawaited(() async {
          try {
            await undo(snapshot);
          } catch (_) {
            if (messenger.mounted) showOn(messenger, undoFailureMessage);
          }
        }()),
      ),
    ));
  return true;
}
```

Add `import 'dart:async';`. Keep `show`, `showOn`; delete `showUndo` once no caller remains (Step 3) and drop its `duration` parameter (never varied).

- [ ] **Step 3: Rewrite the four `actions.dart` files on top of it**

Each public function keeps its name and signature. Example for `shop/actions.dart`:

```dart
Future<void> deleteShoppingItemWithUndo(BuildContext context, WidgetRef ref, ShoppingListItemView item) {
  final repository = ref.read(shoppingRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable(
    context,
    perform: () => repository.deleteRowsWithSnapshot(ids: item.ids, userId: userId),
    undo: (rows) => repository.restoreRows(rows: rows, userId: userId),
    message: '${item.name} removed',
    failureMessage: 'Could not remove ${item.name}. Try again.',
    undoFailureMessage: 'Could not restore ${item.name}.',
  );
}
```

The generic `T` is inferred from the repository return type, so `shop/actions.dart` no longer imports `data/database.dart` and `plan/`/`meals/actions.dart` no longer import `deletion_snapshots.dart`. Keep the haptic calls where they are today (`completeCheckoutWithoutReceipt` fires `mediumImpact` after success → use `onSuccess`; `markCookedWithUndo` fires after success → `onSuccess`; delete paths fire none). `markCookedWithUndo` uses `describeError` for `PantryUnitMismatchException.userMessage`. `deleteRecipeWithUndo` returns the `bool`.

Delete all RN-history doc comments in these four files; keep at most one line per function stating a non-obvious constraint (e.g. "Undo re-adds via addItem, which re-infers expiry").

- [ ] **Step 4: Empty the allowlist and verify**

Set `_featureDataImportAllowlist = <String>{}` in `house_rules_test.dart`.

```bash
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
```
Pay attention to `test/features/{shop,plan,pantry,meals}/*` haptic assertions (`hapticCalls`).

- [ ] **Step 5: Commit**

```bash
git add -A app
git commit -m "♻️ refactor(app): route every destructive action through GleanSnackBar.runUndoable" -m "Four copies of try/catch/snackbar/undo diverged in which context they used after a pop; one helper owns that and features stop importing drift row types."
```

---

### Task 5: Colours and spacing through the theme

**Files:**
- Modify: `app/lib/design_system/tokens.dart` (add camera colour tokens), `app/lib/design_system/theme.dart` (populate them)
- Modify: every file in `_rawColourAllowlist` (Task 1), plus literal paddings at `lib/router/route_error_screen.dart:37`, `lib/bootstrap.dart:105`, `lib/features/shop/widgets/shopping_row.dart:29`, `lib/features/shop/widgets/shop_list_section.dart:110`
- Modify: `app/test/standards/house_rules_test.dart` — empty `_rawColourAllowlist`
- Modify: `app/test/design_system/tokens_test.dart` — assert the three new tokens exist

- [ ] **Step 1: Read `tokens.dart` to find the colour group of `AppTokens`** and add three fields with the same pattern the existing tone pairs use (constructor param, field, `copyWith`, `lerp`):

```dart
/// Over a live camera preview the brand palette is unreadable; these are the
/// only non-brand colours and they stay tokens so a dark theme can retune them.
final Color onCamera;        // white
final Color cameraScrim;     // black at 45% alpha
final Color cameraBackdrop;  // 0xFF111511
```

Populate them in `theme.dart` next to the existing `AppTokens(...)` literal.

- [ ] **Step 2: Write the failing token test**

In `tokens_test.dart` add:
```dart
test('exposes camera overlay tokens', () {
  final tokens = buildGleanTheme().extension<AppTokens>()!;   // use the file's existing accessor
  expect(tokens.onCamera, const Color(0xFFFFFFFF));
  expect(tokens.cameraBackdrop, const Color(0xFF111511));
  expect(tokens.cameraScrim.a, closeTo(0.45, 0.01));
});
```
Run → FAIL. Implement Step 1 → PASS.

- [ ] **Step 3: Replace the raw colours**

| Site | Replace with |
|---|---|
| `FilledButton` foreground `Colors.white` (`shop_add_field`, `sign_in_screen`, `meals_import_screen`, `shop_checkout_bar` TextButton) | delete the override — the `FilledButtonTheme`/`colorScheme.onPrimary` already gives white; if a spinner needs a colour use `colorScheme.onPrimary` |
| `shop_checkout_bar.dart:75,81` white / white70 text on primary | `colorScheme.onPrimary` / `colorScheme.onPrimary.withValues(alpha: 0.7)` |
| `shopping_row.dart:87` check icon | `colorScheme.onPrimary` |
| `scan_screen.dart:114`, `camera_permission_prompt.dart:24` | `context.tokens.cameraBackdrop` |
| `scan_back_button.dart`, `scan_overlay.dart`, `camera_permission_prompt.dart` whites/blacks | `tokens.onCamera`, `tokens.onCamera.withValues(alpha: …)`, `tokens.cameraScrim` |
| `bootstrap.dart:88` `Color(0xFF2E9D63)` | `Theme.of(context).colorScheme.primary` (or `buildGleanTheme().colorScheme.primary` if no context) |
| Literal `EdgeInsets.all(16)`-style paddings at the four sites | `context.tokens.spacing.<nearest>` |

`Colors.transparent` at `shopping_row.dart:80` and `plan_slot_row.dart:46` is allowed and stays.

- [ ] **Step 4: Empty the allowlist and verify**

```bash
rg -n 'Colors\.(?!transparent)\w+|Color\(0x' lib -g '!lib/design_system/**' -g '!*.g.dart'   # expect none
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add -A app
git commit -m "🎨 style(app): source every colour and spacing from the theme" -m "Raw Colors.* and hex literals in features would make a dark theme a codebase-wide edit; the camera overlay gets its own tokens instead of an exemption."
```

---

### Task 6: Built-ins over hand-rolled widgets

**Files:**
- Create: `app/lib/design_system/list_skeleton.dart`
- Delete: `app/lib/design_system/cross_fade.dart`, `app/lib/design_system/list_entrance.dart`, `app/lib/features/pantry/widgets/pantry_skeleton.dart`, `app/lib/features/plan/widgets/plan_skeleton.dart`, `app/lib/features/shop/widgets/shop_skeleton.dart`, `app/lib/features/meals/widgets/meals_skeletons.dart`, `app/lib/features/settings/widgets/settings_skeleton.dart` (move `SettingsLoadError` into `settings_screen.dart`), `app/test/design_system/cross_fade_test.dart`, `app/test/design_system/list_entrance_test.dart`
- Modify: `app/lib/design_system/design_system.dart` barrel; all users listed by `rg -l 'GleanCrossFade|GleanListEntrance|Skeleton\(' lib test`
- Create: `app/test/design_system/list_skeleton_test.dart`

**Interfaces:**
- Produces:
```dart
/// Loading placeholder: an optional header block then [rows] row blocks.
class ListSkeleton extends StatelessWidget {
  const ListSkeleton({super.key, this.rows = 5, this.rowHeight = 64, this.headerHeight, this.padding = true});
}
```

- [ ] **Step 1: Failing test**

```dart
testWidgets('renders header plus rows', (tester) async {
  await tester.pumpWidget(MaterialApp(theme: buildGleanTheme(), home: const ListSkeleton(rows: 3, headerHeight: 88)));
  expect(find.byType(SkeletonBox), findsNWidgets(4));
});
```
Run → FAIL.

- [ ] **Step 2: Implement `ListSkeleton`**

```dart
class ListSkeleton extends StatelessWidget {
  const ListSkeleton({super.key, this.rows = 5, this.rowHeight = 64, this.headerHeight, this.padding = true});
  final int rows; final double rowHeight; final double? headerHeight; final bool padding;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final radius = BorderRadius.circular(tokens.radius.lg);
    return ListView(
      physics: const NeverScrollableScrollPhysics(),
      padding: padding ? EdgeInsets.all(tokens.spacing.lg) : EdgeInsets.zero,
      children: [
        if (headerHeight != null) ...[
          SkeletonBox(width: double.infinity, height: headerHeight!, borderRadius: radius),
          SizedBox(height: tokens.spacing.lg),
        ],
        for (var i = 0; i < rows; i++)
          Padding(
            padding: EdgeInsets.only(bottom: tokens.spacing.sm),
            child: SkeletonBox(width: double.infinity, height: rowHeight, borderRadius: radius),
          ),
      ],
    );
  }
}
```

Replace each per-feature skeleton with `ListSkeleton(...)` using that feature's current row count/height (pantry 4×64 + header 20; plan 5×64 + header 88; shop 5×56; recipe list 4×96; recipe detail → `ListSkeleton(rows: 3, rowHeight: 160, headerHeight: 96)`; settings 3×120 + header 72). Screen tests use `pumpPastSkeleton`/`find.byType(XSkeleton)` — switch them to `find.byType(ListSkeleton)`.

- [ ] **Step 3: Inline `AnimatedSwitcher` where `GleanCrossFade` was used**

At each of the six sites:
```dart
AnimatedSwitcher(
  duration: const Duration(milliseconds: 220),
  child: KeyedSubtree(key: ValueKey(isLoading), child: isLoading ? const ListSkeleton(...) : content),
)
```
Delete `cross_fade.dart` and its test. `bootstrap_test.dart` asserts `find.byType(AnimatedSwitcher)` — keep that assertion if it still holds, else drop it.

- [ ] **Step 4: Delete `GleanListEntrance`**

Remove the wrapper at its three list sites (pantry, shop, meals) — the row becomes the direct list child with the same `key`. Where the comment forced `ListView(children:)` purely for the entrance animation, switch to `ListView.builder` if the list can be long. Delete `list_entrance.dart` and its test.

- [ ] **Step 5: Verify + commit**

```bash
rg -n 'GleanCrossFade|GleanListEntrance|PantrySkeleton|PlanSkeleton|ShopListSkeleton|RecipeListSkeleton|RecipeDetailSkeleton|SettingsSkeleton' lib test   # none
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git add -A app
git commit -m "♻️ refactor(app): one ListSkeleton; AnimatedSwitcher and plain lists replace hand-rolled wrappers" -m "Five near-identical skeletons and two thin animation wrappers added surface without behaviour Flutter does not already ship."
```

---

### Task 7: Router params and route constants

**Files:**
- Modify: `app/lib/router/intake_params.dart` — delete every `operator ==`/`hashCode` override (nav `extra` objects are never compared) and the RN-history comments; keep `ReviewItemDraft.copyWith`.
- Modify: `app/lib/router/app_routes.dart` — delete `tabBranchRoots`, `intakeRoutes`, `all` and their comments. Keep `RouteSpec` and every named route.
- Modify: `app/test/router/route_table_test.dart` — replace references to the deleted lists with inline expectations (five branches, in order `pantry, meals, plan, shop, settings`; intake routes resolve outside the shell). Keep every behavioural assertion.
- Delete: `app/test/router/typed_params_test.dart` (it tested `==`).

- [ ] **Step 1: Make the edits, then verify `router.dart` and `route_table_test.dart` compile without the lists** (`rg -n 'AppRoutes\.(all|intakeRoutes|tabBranchRoots)' lib test` → none).

- [ ] **Step 2: Verify + commit**

```bash
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git add -A app
git commit -m "🔥 refactor(app): drop test-only equality and route lists from the router" -m "Nav extras are never compared and the route lists existed only for one test that can state its expectations inline."
```

---

### Task 8: Onboarding status straight from user_config

**Files:**
- Modify: `app/lib/features/onboarding/providers/onboarding_status.dart` → shrink to one provider
- Modify: `app/lib/features/onboarding/onboarding_screen.dart` (call the repository instead of the store), `app/test/support/harness.dart` (remove the `onboardingStatusStoreProvider` override and whatever `completedOnboarding` parameter fed it; tests that need "already completed" call `harness.container.read(userConfigRepositoryProvider).markOnboardingCompleted(userId)` before pumping)
- Rewrite: `app/test/features/onboarding/onboarding_status_test.dart` against the real fixture (two cases: false by default; true after `markOnboardingCompleted`)
- Modify: `app/test/features/onboarding/onboarding_gate_test.dart`, `onboarding_screen_test.dart`, `test/router/onboarding_gate_wiring_test.dart` as needed for the harness change

**Interfaces:**
- Produces:
```dart
final StreamProvider<bool> hasCompletedOnboardingProvider = StreamProvider<bool>((ref) {
  final userId = ref.watch(currentUserIdProvider);
  return ref.watch(userConfigRepositoryProvider).watchOnboardingCompleted(userId);
});
```

- [ ] **Step 1: Write the replacement status test first** (uses `test/data/fixture.dart` + a `ProviderContainer` with `gleanDatabaseProvider`/`currentUserIdProvider` overrides):

```dart
test('false until markOnboardingCompleted, then true', () async {
  final container = ProviderContainer(overrides: [
    gleanDatabaseProvider.overrideWithValue(db),
    currentUserIdProvider.overrideWithValue('u1'),
  ]);
  addTearDown(container.dispose);
  final sub = container.listen(hasCompletedOnboardingProvider, (_, _) {});
  await container.read(hasCompletedOnboardingProvider.future);
  expect(sub.read().value, isFalse);
  await container.read(userConfigRepositoryProvider).markOnboardingCompleted('u1');
  await Future<void>.delayed(Duration.zero);
  expect(sub.read().value, isTrue);
});
```

- [ ] **Step 2: Delete `OnboardingStatusStore`, both implementations and `onboardingStatusStoreProvider`; implement the provider above; fix the harness and screen.**

- [ ] **Step 3: Verify + commit**

```bash
rg -n 'OnboardingStatusStore|onboardingStatusStoreProvider' lib test   # none
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git add -A app
git commit -m "🔥 refactor(app): read onboarding status straight from user_config" -m "An abstract store with one production adapter and an in-memory fake guarded a single bool column the test fixture already provides for real."
```

---

### Task 9: Repository twins, duplicated capacity, dead code, string literals

**Files:**
- Modify: `app/lib/data/repositories/pantry_repository.dart` (`getAll` = `watchAll(userId).first`, or extract the shared query into a private `_itemsQuery(userId)` used by both), `plan_repository.dart` (`getWeek` from the same query as `watchWeek`; delete `remainingCapacityForWeek` if `rg remainingCapacityForWeek lib` shows only tests use it — otherwise make `planWeekRemainingCapacityProvider` the single implementation and have the repository method delegate to `uncookedCountForWeek` with the config read, **no `?? 5` default**: read the default from wherever `UserConfigRepository` defines it), `recipes_repository.dart` (`getSaved` from `watchSaved`'s query), `shopping_repository.dart` (delete `toggleItem`, `deleteItem` — 0 lib callers; add `enum ShoppingSource { manual, ai, mealPlan }` with `.dbValue` and use it at lines ~231/334 and in `ShoppingListItemView`)
- Modify: `app/lib/features/shop/presentation.dart` (`isPlanDerived` → `item.source == ShoppingSource.mealPlan`)
- Modify: `app/lib/features/plan/presentation.dart` — delete `_isExpiringSoon`, import and call `isExpiringSoon` from `pantry_presentation.dart`
- Modify: `app/lib/api/api_client.dart` — delete `health()`; drop unused `searchRecipes` params (`cuisine`, `dietary`, `page`, `perPage`) and `scanReceipt`'s `contentType`; replace `_multipartBody` with `http.MultipartRequest` + `http.MultipartFile.fromBytes` sent through the existing `_send`/client path (read `_send` first; if it only takes `http.Request`, add a `StreamedResponse` branch rather than keeping the hand-rolled body)
- Modify: `app/lib/data/repositories/shopping_repository.dart` `addManualItem` — remove parameters never passed (`rg -n 'addManualItem\(' lib test` first; keep any a test passes).
- Tests: `test/data/shopping_repository_test.dart`, `test/api/glean_api_client_test.dart` (multipart boundary assertions become "request is multipart and contains the bytes"), `test/features/shop/presentation_test.dart`.

- [ ] **Step 1: For each twin, write the dedupe so `watchX` and `getX` share one query builder. Run `flutter test test/data/` after each file.**
- [ ] **Step 2: Dead code and enum.** Run the full suite.
- [ ] **Step 3: Multipart via the library.** Run `flutter test test/api/`.
- [ ] **Step 4: Commit**

```bash
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git add -A app
git commit -m "♻️ refactor(app): dedupe repository queries, type shopping source, drop dead API surface" -m "Watch/get twins and two capacity implementations had already diverged on defaults; untyped source strings and unused parameters were surface nobody called."
```

---

### Task 10: Collapse the auth seams

**Files:**
- Delete: `app/lib/auth/app_auth_gateway.dart`, `app/lib/auth/session_overrides.dart`, `app/test/auth/auth_wiring_test.dart`, `app/test/auth/auth_mode_test.dart`, `app/lib/features/settings/providers/sign_out_action.dart`
- Modify: `app/lib/auth/cognito_auth_client.dart` (take `FlutterAppAuth appAuth = const FlutterAppAuth()`), `app/lib/auth/token_storage.dart` (delete the abstract class; `SecureTokenStorage` becomes `TokenStorage`, a concrete class over `FlutterSecureStorage`), `app/lib/auth/auth_mode.dart` (keep only `isProductionApiBaseUrl`; move `kAuthBypassUserSub` into `auth_bypass.dart`; delete `AuthSession`, `StoredAuthValues`, `AuthSessionSource`, `resolveAuthSession`), `app/lib/auth/auth_controller.dart`, `app/lib/router/auth_state.dart`, `app/lib/data/providers/database_providers.dart` (`currentUserIdProvider` default), `app/lib/api/providers/api_providers.dart` (`apiAccessTokenProvider` default), `app/lib/main.dart`, `app/lib/main_e2e.dart`, `app/lib/auth/auth.dart` barrel, `app/lib/features/settings/settings_screen.dart` (+ `widgets/account_section.dart`) to call `ref.read(authControllerProvider.notifier).signOut()`
- Modify tests: `test/auth/support/fakes.dart` (replace `InMemoryTokenStorage` with `FlutterSecureStorage.setMockInitialValues({})` + real `TokenStorage`; replace the gateway fake with `class MockFlutterAppAuth extends Mock implements FlutterAppAuth`), `auth_controller_test.dart`, `cognito_auth_client_test.dart`, `token_storage_test.dart`, `session_races_test.dart` (**keep all its cases**), `restart_access_test.dart` (**keep**), `test/support/harness.dart` (override `authControllerProvider` with a seeded active controller instead of `authStatusProvider`), `test/router/auth_redirect_test.dart`, `auth_rejection_recovery_test.dart`, `test/features/auth/*`, `test/features/settings/settings_screen_test.dart`.

**Interfaces:**
- Produces:

```dart
// auth_controller.dart
class AuthController extends Notifier<AuthSessionSnapshot> {
  AuthController(this._seed, {required TokenStorage storage, required CognitoAuthClient client})
      : _storage = storage, _client = client;
  // signIn / signOut / getValidAccessToken unchanged in behaviour; _publish just sets state.
}
final authControllerProvider = NotifierProvider<AuthController, AuthSessionSnapshot>(
  () => throw UnimplementedError('override authControllerProvider from main.dart / main_e2e.dart / the test harness'),
);

// router/auth_state.dart
enum AuthStatus { signedOut, active, expired }
final Provider<AuthStatus> authStatusProvider = Provider((ref) => ref.watch(authControllerProvider).status);

// data/providers/database_providers.dart
final Provider<String> currentUserIdProvider = Provider((ref) {
  final id = ref.watch(authControllerProvider.select((s) => s.userId));
  if (id == null) throw StateError('currentUserIdProvider read while signed out');
  return id;
});

// api/providers/api_providers.dart
final Provider<AccessTokenProvider> apiAccessTokenProvider =
    Provider((ref) => ref.watch(authControllerProvider.notifier).getValidAccessToken);
```

`main.dart` then overrides exactly two providers: `apiBaseUrlProvider` and `authControllerProvider`. `main_e2e.dart` overrides the same two, seeding the bypass snapshot with a `TokenStorage` and `CognitoAuthClient` that are never used (tokens are null) — construct them with `GleanConfig` values as today's production path does.

Tests that previously drove `authStatusProvider.notifier.setStatus(...)` now drive `container.read(authControllerProvider.notifier)` with `signOut()` / a seeded `expired` snapshot. If a test needs to flip status arbitrarily, add a `@visibleForTesting void debugSetSnapshot(AuthSessionSnapshot s) => state = s;` on `AuthController` rather than keeping a second notifier.

- [ ] **Step 1: Convert `fakes.dart` and `token_storage_test.dart` to the concrete `TokenStorage` over `FlutterSecureStorage.setMockInitialValues`. Run `flutter test test/auth/token_storage_test.dart`.**
- [ ] **Step 2: Delete the gateway; mock `FlutterAppAuth` with mocktail in `cognito_auth_client_test.dart`. Run it.** (Register fallback values for `AuthorizationTokenRequest`/`TokenRequest` with `registerFallbackValue`.)
- [ ] **Step 3: Collapse the providers per the Interfaces block; delete `session_overrides.dart`, `SeededAuthStatusNotifier`, `AuthStatusNotifier`, `sign_out_action.dart`; rewrite `main.dart`/`main_e2e.dart`; shrink `auth_mode.dart`.**
- [ ] **Step 4: Fix the harness and every auth/router test. Run `flutter test test/auth test/router test/features/auth test/features/settings`.** `session_races_test.dart` and `restart_access_test.dart` must still contain every case they had; only construction changes.
- [ ] **Step 5: Verify + commit**

```bash
rg -n 'AppAuthGateway|SeededAuthStatusNotifier|sessionOverrides|signOutActionProvider|resolveAuthSession|AuthStatusNotifier' lib test   # none
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git add -A app
git commit -m "♻️ refactor(auth): one AuthController behind one override; drop single-adapter seams" -m "Gateway, storage interface, seeded status notifier and sign-out typedef each had one production adapter; status, user id and token provider are all derivable from the controller."
```

---

### Task 11: Strip process-citation prose

**Files:**
- Modify: every file in `_citationAllowlist` (~128), plus any lib file whose comments narrate RN history
- Modify: `app/test/standards/house_rules_test.dart` — set `_citationAllowlist = <String>{}` and delete the three `const Set` allowlists plus the "allowlist entries that no longer violate" branch, since all three are now empty. Rename `_expectRatchet` → `_expectNone` taking no allowlist.

- [ ] **Step 1: Mechanical pass, file by file.** For each file: open it, and for every comment block decide: does it state a constraint or non-obvious reason that is true of the code *now*? Keep that sentence, drop the citation and the history. Otherwise delete the whole comment. Typical outcome: a 25-line doc comment becomes 0–2 lines. Delete `library;` directives whose only purpose was to host a doc comment.
- [ ] **Step 2: Verify the count and the suite**

```bash
rg -c 'AC-[A-Z]+-\d+|\bR-\d\d\b|\bF-\d\d\b|FINDINGS\.md|REMEDIATION\.md|\.scratch/|\bWave \d|orchestrator' lib -g '!*.g.dart'   # no output
find lib -name '*.dart' -not -name '*.g.dart' | xargs cat | grep -cE '^\s*//'   # expect < 900 (was 2887)
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add -A app
git commit -m "✂️ docs(app): strip process citations and RN history from code comments" -m "Seventeen percent of lib was comments pointing at tickets and a deleted app; comments now state only the constraint that holds today."
```

---

### Task 12: Merge settings and intake widget fragments

**Files:**
- `app/lib/features/settings/widgets/` — merge `section_label.dart` into the card that uses it; merge `integer_slider_control.dart` + `preference_slider_card.dart` + `tolerance_card.dart` into one `PreferenceSliderCard`; merge `dietary_flags_control.dart` into `dietary_preferences_card.dart`; keep `account_section.dart`, `legal_links_section.dart`, `max_time_field.dart`, `settings_stats_row.dart`. Target: 11 files → 6.
- `app/lib/features/intake/widgets/` — merge `scan_back_button.dart` into `scan_overlay.dart`; merge `review_items_list.dart` into `review_item_row.dart` only if the list is < 40 lines.
- Tests: `test/features/settings/settings_screen_test.dart` must pass unchanged (it finds by text/semantics, not by private widget type — check and adjust only `find.byType` references).

- [ ] **Step 1: Merge, keeping every `const` constructor so rebuild scopes are unchanged.**
- [ ] **Step 2: Verify + commit**

```bash
flutter analyze && dart format --output=none --set-exit-if-changed lib test integration_test && memcap flutter test --reporter compact 2>&1 | tail -3
git add -A app
git commit -m "♻️ refactor(app): merge single-use widget fragments in settings and intake" -m "Eleven files for one settings screen split by layout row rather than by responsibility."
```

---

### Task 13 (optional, last): `json_serializable` for `lib/api/models`

**Files:**
- Modify: `app/pubspec.yaml` (add `json_annotation` dependency, `json_serializable` dev dependency), the five files under `app/lib/api/models/`, `app/analysis_options.yaml` already excludes `*.g.dart`.
- Tests: `test/api/glean_api_client_test.dart` must pass unchanged.

- [ ] **Step 1:** Annotate each model with `@JsonSerializable(fieldRename: FieldRename.snake)`, add `part 'x.g.dart';`, replace hand `fromJson`/`toJson` with the generated `_$XFromJson`/`_$XToJson`. Keep any custom parsing (nullable `recipe_id`, defaults) via `@JsonKey`.
- [ ] **Step 2:** `dart run build_runner build --delete-conflicting-outputs`, then the standard verify line, then commit:

```bash
git add -A app
git commit -m "♻️ refactor(api): generate JSON codecs with json_serializable" -m "Six hundred lines of hand-written fromJson duplicated what codegen the project already runs for drift can produce."
```

---

### Final check (after the last task)

```bash
cd /home/ruaridh/glean/.worktrees/flutter-simplify/app
find lib -name '*.dart' -not -name '*.g.dart' | xargs cat | wc -l       # target ≤ 11,500
find lib -name '*.dart' -not -name '*.g.dart' | wc -l                   # target ≤ 110
flutter analyze; dart format --output=none --set-exit-if-changed lib test integration_test; memcap flutter test --reporter compact 2>&1 | tail -3
git log --oneline flutter/rebase-on-main..HEAD
```

Then run the whole-branch review per the subagent-driven-development skill and report: lines before/after per layer, every test file deleted and why, and anything from the Review Focus list that could not be pinned.
