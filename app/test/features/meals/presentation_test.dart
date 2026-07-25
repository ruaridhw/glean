// Ported from `mobile/tests/meals/presentation.test.ts` — real-outcome
// assertions for the pure formatting helpers (AC-TEST-05).
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/features/meals/presentation.dart';

void main() {
  group('getRecipeMeta', () {
    test('formats recipe metadata from real fields', () {
      final List<RecipeMetaItem> meta = getRecipeMeta(
        totalTimeMins: 30,
        yieldCount: 4,
        difficulty: 'easy',
      );
      expect(
        meta.map((RecipeMetaItem item) => (item.icon, item.label)).toList(),
        <(IconData, String)>[
          (Icons.access_time_rounded, '30 min'),
          (Icons.people_outline_rounded, '4 servings'),
          (Icons.speed_rounded, 'easy'),
        ],
      );
    });

    test('omits absent fields', () {
      final List<RecipeMetaItem> meta = getRecipeMeta(
        totalTimeMins: null,
        yieldCount: null,
        difficulty: null,
      );
      expect(meta, isEmpty);
    });
  });

  group('getRecipeTags', () {
    test('derives tags from cuisine and dietary flags', () {
      expect(
        getRecipeTags(
          cuisine: 'Italian',
          dietaryFlags: const <String>['Vegetarian'],
        ),
        <String>['Italian', 'Vegetarian'],
      );
    });

    test('omits a null/empty cuisine', () {
      expect(
        getRecipeTags(cuisine: null, dietaryFlags: const <String>['vegan']),
        <String>['vegan'],
      );
    });
  });

  group('formatIngredientLine', () {
    test('formats ingredients with preparation and optional marker', () {
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'tomato',
            quantity: 2,
            unit: 'whole',
            preparation: 'chopped',
          ),
        ),
        '2 whole tomato, chopped',
      );
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'tomato',
            quantity: 2,
            unit: 'whole',
            preparation: 'chopped',
            isOptional: true,
          ),
        ),
        '2 whole tomato, chopped (optional)',
      );
    });

    test('formats count ingredients with x notation', () {
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'tomato',
            quantity: 6,
            unit: 'pcs',
            preparation: 'chopped',
          ),
        ),
        '6x tomato, chopped',
      );
    });

    test('formats imported canonical units and package context', () {
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'Chickpeas',
            quantity: 800,
            unit: 'g',
            preparation: '2 cans',
          ),
        ),
        '800g Chickpeas, 2 cans',
      );
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'Garlic Clove',
            quantity: 2,
            unit: 'pcs',
          ),
        ),
        '2x Garlic Clove',
      );
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'British Beef Mince',
            quantity: 240,
            unit: 'g',
          ),
        ),
        '240g British Beef Mince',
      );
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'Ginger',
            quantity: 3,
            unit: 'cm',
          ),
        ),
        '3cm Ginger',
      );
    });

    test('omits empty quantity and unit for pantry basics', () {
      expect(
        formatIngredientLine(
          const IngredientLine(
            canonicalName: 'olive oil',
            quantity: 0,
            unit: '',
          ),
        ),
        'olive oil',
      );
    });
  });

  group('describeRecipeSearchError', () {
    test('a 5xx server rejection reads as a server error', () {
      expect(
        describeRecipeSearchError(
          const ApiServerException(statusCode: 500, message: 'boom'),
        ),
        'Search failed because the server returned an error.',
      );
    });

    test('anything else reads as a connection problem', () {
      expect(
        describeRecipeSearchError(const ApiNetworkException('offline')),
        'Search failed. Check your connection and try again.',
      );
    });
  });
}
