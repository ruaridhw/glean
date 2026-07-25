// Real-outcome tests for user config defaults and persistence, ported from
// the "no row yet" fallback intent of `mobile/src/db/config.ts`.
import 'package:glean/data/database.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixture.dart';

void main() {
  group('UserConfigRepository', () {
    late GleanDatabase db;
    late UserConfigRepository repository;
    const userId = 'user-a';

    setUp(() {
      db = createTestDatabase();
      repository = UserConfigRepository(db);
    });

    tearDown(() => db.close());

    test('returns defaults before any row has been saved', () async {
      final config = await repository.get(userId);

      expect(config.mealsPerWeek, UserConfigView.defaultMealsPerWeek);
      expect(config.preferredServings, UserConfigView.defaultPreferredServings);
      expect(config.purchaseTolerance, UserConfigView.defaultPurchaseTolerance);
      expect(config.dietaryFlags, isEmpty);
      expect(config.maxActiveTimeMins, isNull);
    });

    test(
      'save persists and round-trips every field, including dietary flags',
      () async {
        await repository.save(
          const UserConfigView(
            id: userId,
            purchaseTolerance: 0.2,
            preferredServings: 4,
            mealsPerWeek: 7,
            dietaryFlags: ['vegetarian', 'gluten_free'],
            maxActiveTimeMins: 45,
          ),
        );

        final config = await repository.get(userId);
        expect(config.purchaseTolerance, 0.2);
        expect(config.preferredServings, 4);
        expect(config.mealsPerWeek, 7);
        expect(config.dietaryFlags, ['vegetarian', 'gluten_free']);
        expect(config.maxActiveTimeMins, 45);
      },
    );

    test('a second save overwrites rather than duplicating the row', () async {
      await repository.save(UserConfigView.defaults(userId));
      await repository.save(
        const UserConfigView(
          id: userId,
          purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
          preferredServings: 3,
          mealsPerWeek: UserConfigView.defaultMealsPerWeek,
          dietaryFlags: [],
          maxActiveTimeMins: null,
        ),
      );

      final rows = await db.select(db.userConfig).get();
      expect(rows, hasLength(1));
      expect(rows.single.preferredServings, 3);
    });

    test("does not affect another user's config", () async {
      await repository.save(
        const UserConfigView(
          id: userId,
          purchaseTolerance: UserConfigView.defaultPurchaseTolerance,
          preferredServings: 6,
          mealsPerWeek: UserConfigView.defaultMealsPerWeek,
          dietaryFlags: [],
          maxActiveTimeMins: null,
        ),
      );

      final other = await repository.get('user-b');
      expect(other.preferredServings, UserConfigView.defaultPreferredServings);
    });
  });
}
