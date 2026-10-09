// Widget tests for the Settings screen's headline behaviour changes:
// auto-save with no Save button, commit-on-release (not per drag frame),
// surfaced save failures, the cooking-time bound/unit, no Terms/Privacy
// links until those pages exist, and sign-out leaving local data untouched.
//
// Every direct repository call made *from the test body* (as opposed to
// through the widget's own pumped interactions) is wrapped in
// `tester.runAsync`. Without it, a bare `await` on a real drift query here
// hangs indefinitely: `flutter_test` runs widget tests inside a `FakeAsync`
// zone so `tester.pump` can deterministically drive timers/microtasks, and
// with `SettingsScreen` holding a *live* `userConfigProvider` subscription
// (a drift `.watch()` stream) for the whole test, a manual query queued
// behind that stream's own internal bookkeeping on the same connection never
// gets a turn unless something (`runAsync` stepping outside the fake zone,
// or `tester.pump`) drives it forward. This is what timed out the suite at
// 10 minutes before the fix — not a debounce, and not a leaked production
// timer (verified: `_maxTimeDebounce` is cancelled in `dispose()`).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/settings/providers/sign_out_action.dart';
import 'package:glean/features/settings/settings_presentation.dart';
import 'package:glean/features/settings/settings_screen.dart';
import 'package:glean/features/settings/widgets/max_time_field.dart';

import '../../data/fixture.dart';

const String _userId = 'user-1';
const Key _dinnersSliderKey = Key('settings.dinnersSlider');

/// Throws on `save`, leaving `watch`/`get` real — simulates a config-save
/// failure (AC-SET-03) without needing to break the whole in-memory DB.
class _ThrowingUserConfigRepository extends UserConfigRepository {
  _ThrowingUserConfigRepository(super.db);

  @override
  Future<void> save(UserConfigView config) {
    throw Exception('disk full');
  }
}

Widget _buildApp({
  required GleanDatabase db,
  Haptics? haptics,
  SignOutAction? signOut,
  bool throwOnSave = false,
}) {
  return ProviderScope(
    overrides: [
      gleanDatabaseProvider.overrideWithValue(db),
      currentUserIdProvider.overrideWithValue(_userId),
      if (haptics != null) hapticsProvider.overrideWithValue(haptics),
      if (signOut != null) signOutActionProvider.overrideWithValue(signOut),
      if (throwOnSave)
        userConfigRepositoryProvider.overrideWithValue(
          _ThrowingUserConfigRepository(db),
        ),
    ],
    child: MaterialApp(theme: gleanLightTheme, home: const SettingsScreen()),
  );
}

/// Settings' loading skeleton pulses forever (`SkeletonBox`'s
/// `TweenAnimationBuilder`), so `pumpAndSettle()` before it's swapped out
/// would hang. Pump in small fixed steps until it's gone instead.
Future<void> _waitForContent(WidgetTester tester) async {
  for (var i = 0; i < 30; i++) {
    await tester.pump(const Duration(milliseconds: 50));
    if (find.byType(SkeletonBox).evaluate().isEmpty) return;
  }
  fail('Settings content never appeared past the loading skeleton.');
}

/// Runs a direct repository call outside the test's `FakeAsync` zone — see
/// the file-level doc comment for why a bare `await` on one of these hangs
/// whenever a widget in the tree holds a live drift `.watch()` subscription.
Future<T> _readDb<T>(WidgetTester tester, Future<T> Function() query) async {
  final T? result = await tester.runAsync(query);
  if (result == null) {
    fail('tester.runAsync did not run the query (unsupported binding).');
  }
  return result;
}

/// Unmounts the tree, then drains the timer drift schedules while tearing down
/// its stream subscriptions.
///
/// `SettingsScreen` holds a live `userConfigProvider` subscription (a drift
/// `.watch()` stream). Unmounting disposes the `ProviderScope`, which disposes
/// the `StreamProvider` element, which cancels the drift stream — and
/// `StreamQueryStore.markAsClosed` schedules a zero-duration timer to finish
/// the bookkeeping. Ending a test with the screen still mounted therefore
/// leaves that timer pending, trips `!timersPending`, and then wedges the
/// isolate so the whole *file* times out rather than just the one test.
///
/// The zero duration is the tell: it is drift's cleanup, not this screen's
/// 500ms auto-save debounce (which `dispose()` does cancel). See
/// `.scratch/flutter-port/FINDINGS.md` F-12 — this was misdiagnosed as a leaked
/// app timer more than once.
Future<void> _releaseTree(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox.shrink());
  // A `pump`, deliberately, not `runAsync`: the pending timer is a *FakeTimer*
  // (drift's `Timer.run` is intercepted by the zone), and `runAsync` steps
  // outside that zone, which is exactly where it will never be serviced.
  // Advancing fake time is what drains it — and it must be a non-zero advance,
  // because the timer is scheduled *during* the unmount pump above
  // (ProviderScope disposal -> StreamProvider dispose -> drift markAsClosed),
  // so it is queued at the current instant rather than before it.
  await tester.pump(const Duration(milliseconds: 1));
}

/// `testWidgets` with a guaranteed tree release.
///
/// The release has to happen *inside* the test body: the binding verifies
/// `!timersPending` before any `addTearDown` callback runs, so registering the
/// cleanup as a teardown is too late — it still trips the assertion.
void _settingsWidgetTest(
  String description,
  Future<void> Function(WidgetTester tester) body,
) {
  testWidgets(description, (WidgetTester tester) async {
    try {
      await body(tester);
    } finally {
      await _releaseTree(tester);
    }
  });
}

void main() {
  late GleanDatabase db;

  setUp(() => db = createTestDatabase());
  tearDown(() => db.close());

  group('SettingsScreen auto-save', () {
    _settingsWidgetTest(
      'has no Save button; a slider commits once on release, not per drag '
      'frame (AC-SET-01, AC-SET-02, AC-TEST-12)',
      (WidgetTester tester) async {
        await tester.binding.setSurfaceSize(const Size(420, 2000));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        final haptics = RecordingHaptics();
        await tester.pumpWidget(_buildApp(db: db, haptics: haptics));
        await _waitForContent(tester);

        expect(find.text('Save settings'), findsNothing);
        expect(find.text('Save'), findsNothing);

        final TestGesture gesture = await tester.startGesture(
          tester.getCenter(find.byKey(_dinnersSliderKey)),
        );
        await gesture.moveBy(const Offset(60, 0));
        await tester.pump();
        await gesture.moveBy(const Offset(60, 0));
        await tester.pump();
        await gesture.moveBy(const Offset(60, 0));
        await tester.pump();

        // Mid-drag: steps have fired, but nothing has been committed yet.
        expect(haptics.calls, contains(HapticWeight.selection));
        expect(haptics.calls, isNot(contains(HapticWeight.medium)));

        await gesture.up();
        await tester.pump();

        // Exactly one commit for the whole gesture.
        expect(haptics.calls.where((w) => w == HapticWeight.medium).length, 1);

        final saved = await _readDb(
          tester,
          () => UserConfigRepository(db).get(_userId),
        );
        expect(
          saved.mealsPerWeek,
          greaterThan(UserConfigView.defaultMealsPerWeek),
        );
      },
    );

    _settingsWidgetTest(
      'a dietary chip toggle fires selectionClick (not mediumImpact) and '
      'still auto-saves immediately (AC-HAP-05)',
      (WidgetTester tester) async {
        await tester.binding.setSurfaceSize(const Size(420, 2000));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        final haptics = RecordingHaptics();
        await tester.pumpWidget(_buildApp(db: db, haptics: haptics));
        await _waitForContent(tester);

        await tester.tap(find.text('Vegetarian'));
        await tester.pump();

        expect(haptics.calls, <HapticWeight>[HapticWeight.selection]);

        final saved = await _readDb(
          tester,
          () => UserConfigRepository(db).get(_userId),
        );
        expect(saved.dietaryFlags, <String>['Vegetarian']);
      },
    );

    _settingsWidgetTest(
      'switching away and back shows the persisted value, never a stale '
      'unsaved copy',
      (WidgetTester tester) async {
        await tester.binding.setSurfaceSize(const Size(420, 2000));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        await tester.runAsync(
          () => UserConfigRepository(db).save(
            const UserConfigView(
              id: _userId,
              purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
              preferredServings: UserConfigView.defaultPreferredServings,
              mealsPerWeek: 7,
              dietaryFlags: <String>[],
              maxActiveTimeMins: null,
            ),
          ),
        );

        await tester.pumpWidget(_buildApp(db: db));
        await _waitForContent(tester);

        final Slider slider = tester.widget<Slider>(
          find.byKey(_dinnersSliderKey),
        );
        expect(slider.value, 7.0);

        // Unmount entirely, then remount a fresh screen instance against
        // the same underlying database.
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pumpWidget(_buildApp(db: db));
        await _waitForContent(tester);

        final Slider reloaded = tester.widget<Slider>(
          find.byKey(_dinnersSliderKey),
        );
        expect(reloaded.value, 7.0);
      },
    );

    _settingsWidgetTest(
      'a config-save failure surfaces a visible error (AC-SET-03)',
      (WidgetTester tester) async {
        await tester.binding.setSurfaceSize(const Size(420, 2000));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        final haptics = RecordingHaptics();
        await tester.pumpWidget(
          _buildApp(db: db, haptics: haptics, throwOnSave: true),
        );
        await _waitForContent(tester);

        await tester.tap(find.text('Vegan'));
        await tester.pump();

        expect(
          find.text('Could not save your settings. Try again.'),
          findsOneWidget,
        );
        // A failed save must not claim success.
        expect(haptics.calls, isNot(contains(HapticWeight.medium)));
      },
    );
  });

  group('SettingsScreen cooking-time bound (AC-UX-05)', () {
    _settingsWidgetTest(
      'shows the minutes unit and the 1-480 bound before it is violated',
      (WidgetTester tester) async {
        await tester.binding.setSurfaceSize(const Size(420, 2000));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        await tester.pumpWidget(_buildApp(db: db));
        await _waitForContent(tester);

        expect(find.text('min'), findsOneWidget);
        expect(find.text(MaxTimeField.boundHint), findsOneWidget);
      },
    );

    _settingsWidgetTest('rejects an out-of-range value and never persists it', (
      WidgetTester tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(420, 2000));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(_buildApp(db: db));
      await _waitForContent(tester);

      await tester.enterText(find.byType(TextField), '9999');
      await tester.pump();

      expect(
        find.text(
          'Max active time must be between '
          '${SettingsOptionRanges.maxActiveTimeMins.min} and '
          '${SettingsOptionRanges.maxActiveTimeMins.max}',
        ),
        findsOneWidget,
      );

      // Let the debounce window pass — an invalid value must never reach
      // the repository even after the debounce fires.
      await tester.pump(const Duration(milliseconds: 700));

      final saved = await _readDb(
        tester,
        () => UserConfigRepository(db).get(_userId),
      );
      expect(saved.maxActiveTimeMins, isNull);
    });

    _settingsWidgetTest('a valid value auto-saves after the debounce window', (
      WidgetTester tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(420, 2000));
      addTearDown(() => tester.binding.setSurfaceSize(null));

      await tester.pumpWidget(_buildApp(db: db));
      await _waitForContent(tester);

      await tester.enterText(find.byType(TextField), '45');
      await tester.pump(const Duration(milliseconds: 700));

      final saved = await _readDb(
        tester,
        () => UserConfigRepository(db).get(_userId),
      );
      expect(saved.maxActiveTimeMins, 45);
    });
  });

  _settingsWidgetTest('shows no Terms or Privacy links until those pages '
      'are hosted', (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(420, 2000));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_buildApp(db: db));
    await _waitForContent(tester);

    expect(find.text('Sign out'), findsOneWidget);
    expect(find.text('Terms of Service'), findsNothing);
    expect(find.text('Privacy Policy'), findsNothing);
  });

  group('Sign out (AC-DATA-09, AC-HAP-05)', () {
    _settingsWidgetTest(
      'calls the AUTH seam, fires a haptic, and touches no local '
      'user data',
      (WidgetTester tester) async {
        await tester.binding.setSurfaceSize(const Size(420, 2000));
        addTearDown(() => tester.binding.setSurfaceSize(null));

        await tester.runAsync(
          () => UserConfigRepository(db).save(
            const UserConfigView(
              id: _userId,
              purchaseTolerance: 0.7,
              preferredServings: 4,
              mealsPerWeek: 6,
              dietaryFlags: <String>['Vegan'],
              maxActiveTimeMins: 30,
            ),
          ),
        );

        var signedOutCalled = false;
        final haptics = RecordingHaptics();
        await tester.pumpWidget(
          _buildApp(
            db: db,
            haptics: haptics,
            signOut: () async {
              signedOutCalled = true;
            },
          ),
        );
        await _waitForContent(tester);

        await tester.tap(find.text('Sign out'));
        await tester.pump();
        await tester.pump();

        expect(signedOutCalled, isTrue);
        expect(haptics.calls, contains(HapticWeight.medium));

        // Sign-out must not wipe local data — the row saved above survives.
        final stillThere = await _readDb(
          tester,
          () => UserConfigRepository(db).get(_userId),
        );
        expect(stillThere.mealsPerWeek, 6);
        expect(stillThere.dietaryFlags, <String>['Vegan']);
      },
    );
  });
}
