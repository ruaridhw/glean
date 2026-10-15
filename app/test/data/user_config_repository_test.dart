// Real-outcome tests for user config defaults and persistence, ported from
// the "no row yet" fallback intent of the Expo app's `src/db/config.ts`
// (see git history).
import 'dart:io';

import 'package:drift/native.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/user_config_view.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:drift/drift.dart' show Value;
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/features/settings/settings_presentation.dart';

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

    test('the group-by-section preference starts off, is scoped per user, and '
        'is remembered after the database is reopened', () async {
      final directory = await Directory.systemTemp.createTemp('glean-pref-');
      addTearDown(() => directory.delete(recursive: true));
      final file = File('${directory.path}/glean.sqlite');

      var fileDb = GleanDatabase(NativeDatabase(file));
      var fileRepository = UserConfigRepository(fileDb);
      expect(
        await fileRepository.watchGroupShoppingBySection(userId).first,
        isFalse,
      );

      await fileRepository.setGroupShoppingBySection(userId, true);
      expect(
        await fileRepository.watchGroupShoppingBySection(userId).first,
        isTrue,
      );
      expect(
        await fileRepository.watchGroupShoppingBySection('user-b').first,
        isFalse,
      );
      await fileDb.close();

      fileDb = GleanDatabase(NativeDatabase(file));
      addTearDown(fileDb.close);
      fileRepository = UserConfigRepository(fileDb);
      expect(
        await fileRepository.watchGroupShoppingBySection(userId).first,
        isTrue,
      );

      await fileRepository.setGroupShoppingBySection(userId, false);
      expect(
        await fileRepository.watchGroupShoppingBySection(userId).first,
        isFalse,
      );
    });

    test(
      'saving settings leaves the group-by-section preference alone',
      () async {
        await repository.setGroupShoppingBySection(userId, true);

        await repository.save(UserConfigView.defaults(userId));

        expect(
          await repository.watchGroupShoppingBySection(userId).first,
          isTrue,
        );
      },
    );

    test('watchOnboardingCompleted is scoped per user', () async {
      await repository.markOnboardingCompleted('user-a');

      expect(await repository.watchOnboardingCompleted('user-a').first, isTrue);
      expect(
        await repository.watchOnboardingCompleted('user-b').first,
        isFalse,
      );
    });

    test('markOnboardingCompleted leaves the other settings intact', () async {
      await repository.save(
        const UserConfigView(
          id: userId,
          purchaseTolerance: 0.2,
          preferredServings: 4,
          mealsPerWeek: 3,
          dietaryFlags: ['vegan'],
          maxActiveTimeMins: 30,
        ),
      );

      await repository.markOnboardingCompleted(userId);

      final config = await repository.get(userId);
      expect(config.mealsPerWeek, 3);
      expect(config.preferredServings, 4);
      expect(config.dietaryFlags, ['vegan']);
      expect(await repository.watchOnboardingCompleted(userId).first, isTrue);
    });

    test(
      'a fresh repository over the same database reads the flag back',
      () async {
        await repository.markOnboardingCompleted(userId);

        final restarted = UserConfigRepository(db);
        expect(await restarted.watchOnboardingCompleted(userId).first, isTrue);
      },
    );

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

    group('a stored legacy "nut-free" choice', () {
      Future<void> storeRaw(String json) => db
          .into(db.userConfig)
          .insert(
            UserConfigCompanion.insert(id: userId, dietaryFlags: Value(json)),
          );

      test('reads back as both the tree-nut and peanut flags', () async {
        await storeRaw('["nut-free"]');

        final config = await repository.get(userId);

        expect(config.dietaryFlags, ['Tree-nut-free', 'Peanut-free']);
      });

      test(
        'is matched whatever its case and keeps the other flags in order',
        () async {
          await storeRaw('["Vegan"," Nut-Free ","Keto"]');

          final config = await repository.get(userId);

          expect(config.dietaryFlags, [
            'Vegan',
            'Tree-nut-free',
            'Peanut-free',
            'Keto',
          ]);
        },
      );

      test('adds no duplicate when a new flag is already stored', () async {
        await storeRaw('["Tree-nut-free","nut-free"]');

        final config = await repository.get(userId);

        expect(config.dietaryFlags, ['Tree-nut-free', 'Peanut-free']);
      });

      test('is written back as the two new flags on the next save', () async {
        await storeRaw('["nut-free"]');

        await repository.save(await repository.get(userId));

        final raw = (await db.select(db.userConfig).getSingle()).dietaryFlags;
        expect(raw, '["Tree-nut-free","Peanut-free"]');
      });

      test('is not turned into a flag the household did not choose', () async {
        await storeRaw('["Peanut-free"]');

        final config = await repository.get(userId);

        expect(config.dietaryFlags, ['Peanut-free']);
      });

      test('shows as both chips the Settings screen offers', () async {
        await storeRaw('["nut-free"]');

        final config = await repository.get(userId);

        expect(config.dietaryFlags, everyElement(isIn(dietaryOptions)));
        expect(dietaryOptions, isNot(contains('Nut-Free')));
      });
    });

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
