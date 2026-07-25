// Unit coverage for the pure Pantry presentation helpers (AC-TEST-05 style
// port), ported from `mobile/src/pantry/presentation.ts`.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/features/pantry/pantry_presentation.dart';

PantryItemView _item({
  int id = 1,
  String foodGroup = 'vegetables',
  String? category = 'leafy_greens',
  DateTime? expiryDate,
  double quantity = 1,
  String unit = 'unit',
}) {
  return PantryItemView(
    id: id,
    userId: 'user-a',
    ingredientId: id,
    quantity: quantity,
    unit: unit,
    unitPrice: null,
    expiryDate: expiryDate,
    lastUsedAt: null,
    updatedAt: DateTime(2026, 1, 1),
    canonicalName: 'spinach',
    isStaple: false,
    category: category,
    foodGroup: foodGroup,
    shelfLifeDays: 5,
  );
}

void main() {
  group('pantryCategoryMeta', () {
    test('vegetables and fruit fold into the same "Veg & Fruit" section', () {
      expect(
        pantryCategoryMeta('vegetables').key,
        pantryCategoryMeta('fruit').key,
      );
      expect(pantryCategoryMeta('vegetables').label, 'Veg & Fruit');
    });

    test('carbohydrates, fats and condiments fold into "Cupboard"', () {
      expect(pantryCategoryMeta('carbohydrates').key, 'cupboard');
      expect(pantryCategoryMeta('fats').key, 'cupboard');
      expect(pantryCategoryMeta('condiments').key, 'cupboard');
    });

    test(
      'an unrecognised food group falls back to "Other", never vanishes',
      () {
        final meta = pantryCategoryMeta('not-a-real-group');
        expect(meta.key, 'other');
        expect(meta.label, 'Other');
      },
    );
  });

  group('groupPantryItems', () {
    test('groups items by display section, preserving first-seen order', () {
      final items = <PantryItemView>[
        _item(id: 1, foodGroup: 'dairy'),
        _item(id: 2, foodGroup: 'vegetables'),
        _item(id: 3, foodGroup: 'fruit'),
        _item(id: 4, foodGroup: 'dairy'),
      ];

      final sections = groupPantryItems(items);

      expect(sections.map((s) => s.meta.key), <String>['dairy', 'veg_fruit']);
      expect(sections[0].items, hasLength(2)); // both dairy items
      expect(sections[1].items, hasLength(2)); // vegetables + fruit item
    });
  });

  group('formatPantryQuantity', () {
    test('drops a trailing ".0" for whole numbers', () {
      expect(formatPantryQuantity(2, 'g'), '2 g');
    });

    test('keeps decimals for fractional quantities', () {
      expect(formatPantryQuantity(1.5, 'kg'), '1.5 kg');
    });
  });

  group('expiryBadgeFor', () {
    final now = DateTime(2026, 1, 10);

    test('null expiry produces no badge (degrade gracefully, F-07/F-08)', () {
      expect(expiryBadgeFor(null, now: now), isNull);
    });

    test('a past date is "Expired"', () {
      final badge = expiryBadgeFor(DateTime(2026, 1, 5), now: now);
      expect(badge!.label, 'Expired');
      expect(badge.tone, ExpiryTone.expired);
    });

    test('today is "Today", tone expired', () {
      final badge = expiryBadgeFor(now, now: now);
      expect(badge!.label, 'Today');
      expect(badge.tone, ExpiryTone.expired);
    });

    test('within 2 days is "soon"', () {
      final badge = expiryBadgeFor(DateTime(2026, 1, 12), now: now);
      expect(badge!.label, '2d left');
      expect(badge.tone, ExpiryTone.soon);
    });

    test('further out is "later"', () {
      final badge = expiryBadgeFor(DateTime(2026, 1, 20), now: now);
      expect(badge!.tone, ExpiryTone.later);
    });
  });

  group('isExpiringSoon', () {
    final now = DateTime(2026, 1, 10);

    test('true for expired/soon, false for later or absent', () {
      expect(
        isExpiringSoon(_item(expiryDate: DateTime(2026, 1, 5)), now: now),
        isTrue,
      );
      expect(
        isExpiringSoon(_item(expiryDate: DateTime(2026, 1, 11)), now: now),
        isTrue,
      );
      expect(
        isExpiringSoon(_item(expiryDate: DateTime(2026, 2, 1)), now: now),
        isFalse,
      );
      expect(isExpiringSoon(_item(expiryDate: null), now: now), isFalse);
    });
  });

  group('parsePositiveQuantity — the single fallback rule (AC-PAN-08/09)', () {
    test('parses a valid decimal', () {
      expect(parsePositiveQuantity('1.5'), 1.5);
    });

    test(
      'rejects zero, negative, non-numeric and blank input — no fallback',
      () {
        expect(parsePositiveQuantity('0'), isNull);
        expect(parsePositiveQuantity('-3'), isNull);
        expect(parsePositiveQuantity('abc'), isNull);
        expect(parsePositiveQuantity(''), isNull);
        expect(parsePositiveQuantity('   '), isNull);
        expect(parsePositiveQuantity('NaN'), isNull);
      },
    );

    test('trims surrounding whitespace', () {
      expect(parsePositiveQuantity('  2  '), 2);
    });
  });

  group('categoryLabel', () {
    test('title-cases each underscore-separated word', () {
      expect(categoryLabel('leafy_greens'), 'Leafy Greens');
      expect(categoryLabel('dairy'), 'Dairy');
    });
  });

  group('formatQuantitySeed', () {
    test('drops a trailing ".0" for whole numbers', () {
      expect(formatQuantitySeed(3), '3');
    });

    test(
      'keeps a decimal value typeable — does not round-trip to an integer',
      () {
        expect(formatQuantitySeed(1.5), '1.5');
      },
    );
  });
}
