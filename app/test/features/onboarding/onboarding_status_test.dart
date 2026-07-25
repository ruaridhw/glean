// Real-outcome tests for the onboarding "have I done this before" seam
// (see `providers/onboarding_status.dart` for why this exists instead of a
// `user_config` column). Exercises `InMemoryOnboardingStatusStore` — the
// same fake widget tests use — rather than `FileOnboardingStatusStore`,
// which talks to a real plugin channel (`path_provider`) that isn't mocked
// under plain `flutter test`.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/features/onboarding/providers/onboarding_status.dart';

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
}
