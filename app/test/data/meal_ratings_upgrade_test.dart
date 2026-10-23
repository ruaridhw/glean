// The schema step that adds meal ratings opens beside a full v6 database, so the owner's cooked history
// and settings must come through it untouched and rateable. The frozen fixture has no ratings table and
// no explainer flag, which is what the upgrade has to add.
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/pantry_repository.dart';
import 'package:glean/data/repositories/plan_repository.dart';
import 'package:glean/data/repositories/user_config_repository.dart';
import 'package:glean/data/util/week.dart';
import 'package:sqlite3/sqlite3.dart';

void main() {
  test(
    'a version 6 file keeps its plan and settings and can rate a cooked meal',
    () async {
      final directory = await Directory.systemTemp.createTemp('glean-v7-');
      addTearDown(() => directory.delete(recursive: true));
      final file = File('${directory.path}/glean.sqlite');
      final old = sqlite3.open(file.path);
      old.execute(File('test/data/fixtures/schema_v6.sql').readAsStringSync());
      old.close();

      final db = GleanDatabase(NativeDatabase(file));
      addTearDown(db.close);
      final ingredients = IngredientsRepository(db);
      final plan = PlanRepository(db, PantryRepository(db, ingredients));
      final config = UserConfigRepository(db);
      const userId = 'reopen-user';

      expect(await config.claimRatingsExplainer(userId), isTrue);
      final entries = await plan.getWeek(
        userId: userId,
        weekStart: startOfWeek(DateTime(2026, 10, 5)),
      );
      final done = entries.singleWhere((entry) => entry.isCooked);
      expect(done.recipeTitle, 'Persisted dinner');
      expect(done.externalIdSnapshot, 'rec_persist');
      expect(done.rating, isNull);

      // The explainer flag is the only thing added to the settings row; the owner's choices survive.
      expect(await config.claimRatingsExplainer(userId), isFalse);
      final saved = await config.get(userId);
      expect(saved.mealsPerWeek, 3);
      expect(saved.preferredServings, 4);
      expect(saved.maxActiveTimeMins, 45);

      await plan.rateWithNote(
        entryId: done.id,
        userId: userId,
        rating: MealThumb.down,
        note: 'too sweet for the kids',
        now: DateTime(2026, 10, 7, 12),
      );

      final rated = (await plan.getWeek(
        userId: userId,
        weekStart: startOfWeek(DateTime(2026, 10, 5)),
      )).singleWhere((entry) => entry.isCooked);
      expect(rated.rating, MealThumb.down);
      expect(rated.note, 'too sweet for the kids');
      // The twelve-week window the planner reads carries the same row, rating included.
      final history = await plan.cookedHistory(
        userId: userId,
        now: DateTime(2026, 10, 7),
      );
      expect(history.single.rating, MealThumb.down);
    },
  );
}
