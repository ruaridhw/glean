// Widget coverage for the Search segment (AC-MEAL-01/07/10): a real inline
// input, live results, and — the core AC-TEST-11 assertion — tapping a
// search result previews it without persisting anything.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockHttpClient extends Mock implements http.Client {}

http.Response _jsonResponse(Object body) => http.Response(
  jsonEncode(body),
  200,
  headers: const {'content-type': 'application/json'},
);

void main() {
  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:9999/'));
  });

  group('MealsScreen — Search segment', () {
    late MockHttpClient httpClient;
    late AppTestHarness harness;
    late RecipesRepository recipes;

    setUp(() {
      httpClient = MockHttpClient();
      harness = AppTestHarness(httpClient: httpClient);
      recipes = RecipesRepository(
        harness.db,
        IngredientsRepository(harness.db),
      );

      when(
        () => httpClient.get(any(), headers: any(named: 'headers')),
      ).thenAnswer((invocation) async {
        final Uri uri = invocation.positionalArguments.first as Uri;
        if (uri.path == '/recipes/search') {
          return _jsonResponse(<String, dynamic>{
            'results': <Map<String, dynamic>>[
              <String, dynamic>{
                'external_id': 'ext-1',
                'title': 'Miso Soup',
                'cuisine': 'Japanese',
                'difficulty': 'easy',
                'total_time_mins': 20,
              },
            ],
            'total': 1,
          });
        }
        if (uri.path == '/recipes/ext-1') {
          return _jsonResponse(<String, dynamic>{
            'external_id': 'ext-1',
            'title': 'Miso Soup',
            'source_url': null,
            'cuisine': 'Japanese',
            'difficulty': 'easy',
            'active_time_mins': 5,
            'total_time_mins': 20,
            'dietary_flags': <String>[],
            'not_suitable_for': <String>['soy'],
            'yield_count': 2,
            'nutrition': null,
            'instructions': <Map<String, dynamic>>[],
            'ingredients': <Map<String, dynamic>>[],
          });
        }
        return http.Response('not found', 404);
      });
    });

    tearDown(() => harness.dispose());

    testWidgets('shows empty and no-results states (AC-MEAL-10)', (
      WidgetTester tester,
    ) async {
      when(
        () => httpClient.get(any(), headers: any(named: 'headers')),
      ).thenAnswer(
        (_) async => _jsonResponse(<String, dynamic>{
          'results': <dynamic>[],
          'total': 0,
        }),
      );

      await harness.pumpAt(tester, AppRoutes.meals.path);
      await tester.pumpAndSettle();
      await tester.tap(find.text('Search'));
      await tester.pumpAndSettle();

      expect(find.text('Search recipes'), findsOneWidget);

      await tester.enterText(find.byType(TextField), 'nonexistent');
      await tester.pump(
        recipeSearchDebounce + const Duration(milliseconds: 50),
      );
      await tester.pumpAndSettle();

      expect(find.text('No recipes found'), findsOneWidget);
    });

    testWidgets(
      'tapping a search result previews it without saving (AC-TEST-11)',
      (WidgetTester tester) async {
        await harness.pumpAt(tester, AppRoutes.meals.path);
        await tester.pumpAndSettle();
        await tester.tap(find.text('Search'));
        await tester.pumpAndSettle();

        await tester.enterText(find.byType(TextField), 'miso');
        await tester.pump(
          recipeSearchDebounce + const Duration(milliseconds: 50),
        );
        await tester.pumpAndSettle();

        expect(find.text('Miso Soup'), findsOneWidget);

        await tester.tap(find.text('Miso Soup'));
        await tester.pumpAndSettle();

        // Preview shows the fetched detail, including allergen info...
        expect(find.textContaining('Not suitable for'), findsOneWidget);
        // ...but nothing was persisted by the mere act of viewing it. (A raw
        // repository stream query in a widget test must go through
        // `tester.runAsync` — see `meals_screen_test.dart`'s comment.)
        expect(
          await tester.runAsync(() => recipes.watchSaved('test-user').first),
          isEmpty,
        );
        expect(find.byIcon(Icons.bookmark_border_rounded), findsOneWidget);

        // Explicitly saving is what commits it.
        await tester.tap(find.byIcon(Icons.bookmark_border_rounded));
        await tester.pumpAndSettle();

        expect(
          await tester.runAsync(() => recipes.watchSaved('test-user').first),
          hasLength(1),
        );
        expect(find.byIcon(Icons.bookmark_rounded), findsOneWidget);
      },
    );
  });
}
