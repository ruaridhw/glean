// Widget coverage for import-from-URL (AC-MEAL-10): a fresh import saves and
// opens the new recipe; an import matching an already-saved `external_id`
// dedupes and says "already saved" instead of inserting a duplicate.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/data/repositories/ingredients_repository.dart';
import 'package:glean/data/repositories/recipes_repository.dart';
import 'package:glean/router/app_routes.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

import '../../support/harness.dart';

class MockHttpClient extends Mock implements http.Client {}

http.Response _importResponse(String externalId, String title) {
  return http.Response(
    jsonEncode(<String, dynamic>{
      'external_id': externalId,
      'title': title,
      'source_url': 'https://example.com/$externalId',
      'cuisine': null,
      'difficulty': null,
      'active_time_mins': null,
      'total_time_mins': null,
      'dietary_flags': <String>[],
      'not_suitable_for': <String>[],
      'yield_count': null,
      'nutrition': null,
      'instructions': <Map<String, dynamic>>[],
      'ingredients': <Map<String, dynamic>>[],
    }),
    200,
    headers: const {'content-type': 'application/json'},
  );
}

void main() {
  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:9999/'));
  });

  group('MealsImportScreen', () {
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
    });

    tearDown(() => harness.dispose());

    Future<void> enterAndImport(WidgetTester tester, String url) async {
      await tester.enterText(find.byType(TextField), url);
      await tester.pump();
      await tester.tap(find.widgetWithText(FilledButton, 'Import'));
      await tester.pumpAndSettle();
    }

    testWidgets('imports a fresh URL and saves exactly one recipe', (
      WidgetTester tester,
    ) async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer((_) async => _importResponse('ext-new', 'Miso Soup'));

      await harness.pumpAt(tester, AppRoutes.mealsImport.path);
      await tester.pumpAndSettle();
      await enterAndImport(tester, 'https://example.com/miso');

      // A raw repository stream query in a widget test must go through
      // `tester.runAsync` — see `meals_screen_test.dart`'s comment.
      expect(
        await tester.runAsync(() => recipes.watchSaved('test-user').first),
        hasLength(1),
      );
      expect(
        find.descendant(
          of: find.byType(AppBar),
          matching: find.text('Miso Soup'),
        ),
        findsOneWidget,
      );
    });

    testWidgets(
      'dedupes an already-saved external id and says "already saved"',
      (WidgetTester tester) async {
        await recipes.save(
          userId: 'test-user',
          externalId: 'ext-dupe',
          title: 'Already Here',
          ingredients: const <SaveRecipeIngredient>[],
        );

        when(
          () => httpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) async => _importResponse('ext-dupe', 'Already Here'));

        await harness.pumpAt(tester, AppRoutes.mealsImport.path);
        await tester.pumpAndSettle();
        await enterAndImport(tester, 'https://example.com/dupe');

        expect(find.text('Already saved'), findsOneWidget);
        // No duplicate row was inserted for the same external id.
        expect(
          await tester.runAsync(() => recipes.watchSaved('test-user').first),
          hasLength(1),
        );
      },
    );
  });
}
