// Ported from the Expo app's `tests/meal-plan/compress.test.ts` (see git
// history) — the pantry
// urgency-scoring/top-N compression that feeds `MealPlanRequest.pantry`
// (FLUTTER_MIGRATION.md's "highest-value logic to port" table).
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/features/plan/compression.dart';

final DateTime _now = DateTime(2026, 4, 7, 12);

PantryItemView _item({
  int ingredientId = 1,
  String canonicalName = 'chicken breast',
  double quantity = 400,
  String unit = 'g',
  DateTime? expiryDate,
  DateTime? lastUsedAt,
  bool isStaple = false,
  String foodGroup = 'protein',
}) {
  return PantryItemView(
    id: ingredientId,
    userId: 'user-a',
    ingredientId: ingredientId,
    quantity: quantity,
    unit: unit,
    unitPrice: null,
    expiryDate: expiryDate,
    lastUsedAt: lastUsedAt,
    updatedAt: _now,
    canonicalName: canonicalName,
    isStaple: isStaple,
    category: 'poultry',
    foodGroup: foodGroup,
    shelfLifeDays: 2,
  );
}

void main() {
  group('scorePantryItem', () {
    test('scores higher when item expires within 1 day', () {
      final expiringSoon = _item(expiryDate: DateTime(2026, 4, 8));
      final notExpiring = _item(expiryDate: DateTime(2026, 4, 20));
      expect(
        scorePantryItem(expiringSoon, now: _now),
        greaterThan(scorePantryItem(notExpiring, now: _now)),
      );
    });

    test('scores higher when item has not been used recently', () {
      final stale = _item(lastUsedAt: DateTime(2026, 3, 7)); // 31 days ago
      final fresh = _item(lastUsedAt: DateTime(2026, 4, 6)); // 1 day ago
      expect(
        scorePantryItem(stale, now: _now),
        greaterThan(scorePantryItem(fresh, now: _now)),
      );
    });

    test('adds 15 points for never-used items', () {
      final neverUsed = _item();
      final recentlyUsed = _item(lastUsedAt: DateTime(2026, 4, 6));
      expect(
        scorePantryItem(neverUsed, now: _now),
        greaterThan(scorePantryItem(recentlyUsed, now: _now)),
      );
    });
  });

  group('compressPantry', () {
    test('excludes staple items', () {
      final items = <PantryItemView>[
        _item(ingredientId: 1, isStaple: true),
        _item(ingredientId: 2, canonicalName: 'salmon'),
      ];
      final result = compressPantry(items, now: _now);
      expect(result, hasLength(1));
      expect(result.single.name, 'salmon');
    });

    test('excludes zero-quantity items', () {
      final items = <PantryItemView>[
        _item(ingredientId: 1, quantity: 0),
        _item(ingredientId: 2, canonicalName: 'salmon', quantity: 200),
      ];
      final result = compressPantry(items, now: _now);
      expect(result, hasLength(1));
      expect(result.single.name, 'salmon');
    });

    test('returns at most topN items sorted by urgency descending', () {
      final items = <PantryItemView>[
        for (int i = 0; i < 20; i++)
          _item(
            ingredientId: i + 1,
            canonicalName: 'ingredient-$i',
            expiryDate: i < 5 ? DateTime(2026, 4, 8) : null,
          ),
      ];
      final result = compressPantry(items, topN: 10, now: _now);
      expect(result, hasLength(10));
      expect(
        result.first.urgencyScore,
        greaterThanOrEqualTo(result.last.urgencyScore),
      );
    });

    test('maps ingredient_id to id in the output', () {
      final items = <PantryItemView>[_item(ingredientId: 42)];
      final result = compressPantry(items, now: _now);
      expect(result.single.id, 42);
    });

    test('carries the food group through unchanged', () {
      final items = <PantryItemView>[_item(foodGroup: 'vegetables')];
      final result = compressPantry(items, now: _now);
      expect(result.single.foodGroup, 'vegetables');
    });
  });
}
