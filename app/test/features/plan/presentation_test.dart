// Unit coverage for the ported Plan presentation logic
// (`mobile/src/plan/presentation.ts`), plus the AC-PLAN-03/04 fix to the
// "left to plan" hint: it must be driven by remaining *capacity*
// (cooked-excluded, per-week), not `target - totalEntries`.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/features/plan/presentation.dart';

MealPlanEntryView _entry({
  int id = 1,
  int? recipeId = 1,
  String recipeTitle = 'Tomato Pasta',
  DateTime? plannedDate,
  DateTime? cookedAt,
  int servings = 2,
}) {
  return MealPlanEntryView(
    id: id,
    userId: 'user-a',
    recipeId: recipeId,
    recipeTitle: recipeTitle,
    plannedDate: plannedDate ?? DateTime(2026, 1, 5),
    cookedAt: cookedAt,
    servings: servings,
  );
}

PantryItemView _pantryItem({
  int id = 1,
  int ingredientId = 1,
  String canonicalName = 'chicken breast',
  DateTime? expiryDate,
  bool isStaple = false,
}) {
  return PantryItemView(
    id: id,
    userId: 'user-a',
    ingredientId: ingredientId,
    quantity: 200,
    unit: 'g',
    unitPrice: null,
    expiryDate: expiryDate,
    lastUsedAt: null,
    updatedAt: DateTime(2026, 1, 1),
    canonicalName: canonicalName,
    isStaple: isStaple,
    category: 'poultry',
    foodGroup: 'protein',
    shelfLifeDays: 2,
  );
}

void main() {
  group('buildPlanSlots', () {
    test('one slot per entry, then empty slots up to target', () {
      final slots = buildPlanSlots(<MealPlanEntryView>[_entry(id: 1)], 3);
      expect(slots, hasLength(3));
      expect(slots[0].entry?.id, 1);
      expect(slots[1].entry, isNull);
      expect(slots[2].entry, isNull);
      // Empty-slot keys are distinct — required for stable widget identity.
      expect(slots[1].key, isNot(slots[2].key));
    });

    test('never produces a negative number of empty slots', () {
      final slots = buildPlanSlots(<MealPlanEntryView>[
        _entry(id: 1),
        _entry(id: 2),
        _entry(id: 3),
      ], 1);
      expect(slots, hasLength(3));
      expect(slots.every((s) => s.entry != null), isTrue);
    });
  });

  group('weekRangeLabel', () {
    test('formats a week within one month as "D–D Mon"', () {
      expect(weekRangeLabel(DateTime(2026, 7, 20)), '20–26 Jul');
    });

    test('formats a week spanning two months as "D Mon – D Mon"', () {
      // 27 Jul 2026 is a Monday; its week runs 27 Jul – 2 Aug.
      expect(weekRangeLabel(DateTime(2026, 7, 27)), '27 Jul – 2 Aug');
    });
  });

  group('isCurrentWeek', () {
    test('true for the week containing now, false otherwise', () {
      final now = DateTime.now();
      final thisMonday = now.subtract(Duration(days: now.weekday - 1));
      expect(
        isCurrentWeek(
          DateTime(thisMonday.year, thisMonday.month, thisMonday.day),
        ),
        isTrue,
      );
      expect(
        isCurrentWeek(thisMonday.subtract(const Duration(days: 7))),
        isFalse,
      );
    });
  });

  group('planHint', () {
    test('reports remaining count when capacity is left', () {
      expect(planHint(2), '2 dinners left to plan this week');
      expect(planHint(1), '1 dinner left to plan this week');
    });

    test('reports "fully planned" once remaining capacity hits zero', () {
      expect(planHint(0), 'Week fully planned — nice');
    });

    test(
      'never goes negative in its own wording even if capacity somehow is',
      () {
        expect(planHint(-1), 'Week fully planned — nice');
      },
    );
  });

  group('planExpiryNudge', () {
    final now = DateTime(2026, 4, 7);

    test('returns null when nothing is expiring soon', () {
      final items = <PantryItemView>[
        _pantryItem(expiryDate: DateTime(2026, 4, 20)),
      ];
      expect(planExpiryNudge(items, now: now), isNull);
    });

    test('singular wording for exactly one urgent item', () {
      final items = <PantryItemView>[
        _pantryItem(canonicalName: 'milk', expiryDate: DateTime(2026, 4, 8)),
      ];
      final nudge = planExpiryNudge(items, now: now);
      expect(nudge, isNotNull);
      expect(nudge!.count, 1);
      expect(nudge.title, '1 item needs using up');
      expect(nudge.message, contains('milk is expiring soon'));
    });

    test('plural wording and a "N more" preview beyond two items', () {
      final items = <PantryItemView>[
        _pantryItem(
          id: 1,
          canonicalName: 'milk',
          expiryDate: DateTime(2026, 4, 7),
        ),
        _pantryItem(
          id: 2,
          canonicalName: 'yoghurt',
          expiryDate: DateTime(2026, 4, 8),
        ),
        _pantryItem(
          id: 3,
          canonicalName: 'spinach',
          expiryDate: DateTime(2026, 4, 8),
        ),
      ];
      final nudge = planExpiryNudge(items, now: now);
      expect(nudge, isNotNull);
      expect(nudge!.count, 3);
      expect(nudge.title, '3 items need using up');
      expect(nudge.message, contains('milk, yoghurt and 1 more'));
    });

    test('an already-expired item counts as urgent', () {
      final items = <PantryItemView>[
        _pantryItem(canonicalName: 'cream', expiryDate: DateTime(2026, 4, 1)),
      ];
      expect(planExpiryNudge(items, now: now), isNotNull);
    });
  });
}
