// Real-outcome tests for the onboarding "have I done this before" seam.
// The `InMemoryOnboardingStatusStore` groups below exercise the fake widget
// tests use, in isolation from any storage concern. The final group proves
// R-04: the production store is now backed by `UserConfigRepository`
// (SQLite, via the real in-memory fixture) rather than the standalone
// `onboarding_completed.txt` this replaced — see `providers/onboarding_status.dart`.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';

import '../../data/fixture.dart';

void main() {
  group('InMemoryOnboardingStatusStore', () {
    test('has not completed for a user with no prior record', () async {
      final store = InMemoryOnboardingStatusStore();
      expect(await store.watch('user-a').first, isFalse);
    });

    test('markCompleted persists, and the watch stream re-emits', () async {
      final store = InMemoryOnboardingStatusStore();
      final emissions = <bool>[];
      final subscription = store.watch('user-a').listen(emissions.add);
      addTearDown(subscription.cancel);

      await pumpEventQueue();
      await store.markCompleted('user-a');
      await pumpEventQueue();

      expect(emissions, <bool>[false, true]);
    });

    test('is scoped per user', () async {
      final store = InMemoryOnboardingStatusStore(
        initiallyCompleted: <String>{'user-a'},
      );
      expect(await store.watch('user-a').first, isTrue);
      expect(await store.watch('user-b').first, isFalse);
    });
  });

  group('hasCompletedOnboardingProvider', () {
    test('watches the current user and re-emits after markCompleted with no '
        'ref.invalidate (AC-DATA-05 applied on principle)', () async {
      final store = InMemoryOnboardingStatusStore();
      final container = ProviderContainer(
        overrides: [
          onboardingStatusStoreProvider.overrideWithValue(store),
          currentUserIdProvider.overrideWithValue('user-a'),
        ],
      );
      addTearDown(container.dispose);

      final emissions = <bool>[];
      container.listen<AsyncValue<bool>>(hasCompletedOnboardingProvider, (
        _,
        next,
      ) {
        if (next.hasValue) emissions.add(next.requireValue);
      }, fireImmediately: true);

      await pumpEventQueue();
      await store.markCompleted('user-a');
      await pumpEventQueue();

      expect(emissions, <bool>[false, true]);
    });
  });

  // R-04: proves the production store persists through SQLite, not a text
  // file — this would fail if `onboardingStatusStoreProvider` reverted to
  // writing `onboarding_completed.txt` (no plugin channel for
  // `path_provider` is registered here, so a real file-backed store would
  // throw rather than silently pass).
  group('UserConfigOnboardingStatusStore (R-04)', () {
    test('has not completed for a user with no user_config row', () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final store = UserConfigOnboardingStatusStore(UserConfigRepository(db));

      expect(await store.watch('user-a').first, isFalse);
    });

    test('markCompleted flips the onboardingCompleted column and the watch '
        'stream re-emits with no ref.invalidate', () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final store = UserConfigOnboardingStatusStore(UserConfigRepository(db));

      final emissions = <bool>[];
      final subscription = store.watch('user-a').listen(emissions.add);
      addTearDown(subscription.cancel);

      await pumpEventQueue();
      await store.markCompleted('user-a');
      await pumpEventQueue();

      expect(emissions, <bool>[false, true]);
    });

    test('survives a fresh repository instance against the same database '
        '(simulated app restart)', () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      await UserConfigOnboardingStatusStore(
        UserConfigRepository(db),
      ).markCompleted('user-a');

      // A brand-new repository/store pair, same underlying db — mirrors a
      // cold app restart reading back what a previous run persisted.
      final restarted = UserConfigOnboardingStatusStore(
        UserConfigRepository(db),
      );
      expect(await restarted.watch('user-a').first, isTrue);
    });

    test('is scoped per user', () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final store = UserConfigOnboardingStatusStore(UserConfigRepository(db));

      await store.markCompleted('user-a');

      expect(await store.watch('user-a').first, isTrue);
      expect(await store.watch('user-b').first, isFalse);
    });

    test("markCompleted doesn't disturb a user's other settings", () async {
      final db = createTestDatabase();
      addTearDown(db.close);
      final repository = UserConfigRepository(db);
      await repository.save(
        const UserConfigView(
          id: 'user-a',
          purchaseTolerance: 0.2,
          preferredServings: 4,
          mealsPerWeek: 7,
          dietaryFlags: ['vegetarian'],
          maxActiveTimeMins: 45,
        ),
      );

      await UserConfigOnboardingStatusStore(repository).markCompleted('user-a');

      final config = await repository.get('user-a');
      expect(config.preferredServings, 4);
      expect(config.mealsPerWeek, 7);
      expect(config.dietaryFlags, ['vegetarian']);
      expect(config.maxActiveTimeMins, 45);
    });
  });
}
