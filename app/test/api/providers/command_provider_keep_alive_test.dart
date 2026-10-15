// Regression coverage for FINDINGS.md F-15: every `AsyncNotifierProvider
// .autoDispose` command provider in `lib/api/providers/` must hold itself
// alive for the duration of its own network call (`Ref.keepAlive`), so a
// caller that only `ref.read`s it — never `ref.watch`/`ref.listen`s it, the
// common shape for a fire-and-forget command — still gets a terminal state
// back instead of a disposed-`Ref` crash swallowed inside the notifier.
//
// None of the other provider tests in this directory or in
// `test/api/glean_api_client_test.dart` exercise this: they all hold a
// `ProviderContainer`/subscription reference for the whole test, which
// itself keeps every provider alive and can never reproduce the bug.
// Every test below deliberately does the opposite: it never calls
// `container.listen`/`ref.watch` on the provider under test at all.
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/providers/meal_plan_providers.dart';
import 'package:glean/api/providers/receipts_providers.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/api/providers/shopping_providers.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

class MockHttpClient extends Mock implements http.Client {}

void main() {
  late MockHttpClient httpClient;
  late ProviderContainer container;

  http.Response jsonResponse(Object body) {
    return http.Response(
      jsonEncode(body),
      200,
      headers: {'content-type': 'application/json'},
    );
  }

  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:8000/'));
    registerFallbackValue(
      http.Request('GET', Uri.parse('http://localhost:8000/')),
    );
  });

  setUp(() {
    httpClient = MockHttpClient();
    container = ProviderContainer(
      overrides: [
        apiBaseUrlProvider.overrideWithValue('http://localhost:8000'),
        httpClientProvider.overrideWithValue(httpClient),
      ],
    );
  });

  tearDown(() => container.dispose());

  test('scanReceiptControllerProvider completes and lands its terminal state '
      'when only ref.read (never watched)', () async {
    when(() => httpClient.send(any())).thenAnswer(
      (_) async => http.StreamedResponse(
        Stream.value(
          utf8.encode(
            jsonEncode({
              'items': [
                {
                  'name': 'Milk',
                  'quantity': 1,
                  'unit': 'l',
                  'confidence': 0.9,
                  'food_group': 'dairy',
                },
              ],
            }),
          ),
        ),
        200,
        headers: {'content-type': 'application/json'},
      ),
    );

    // No `container.listen`/`ref.watch` anywhere — exactly the shape that
    // used to get the provider disposed mid-`await`.
    final notifier = container.read(scanReceiptControllerProvider.notifier);
    await notifier.scan(Uint8List.fromList(<int>[1, 2, 3]));

    final state = container.read(scanReceiptControllerProvider);
    expect(state.hasError, isFalse);
    expect(state.value?.items.single.name, 'Milk');
  });

  test('describeReceiptControllerProvider completes and lands its terminal '
      'state when only ref.read (never watched)', () async {
    when(
      () => httpClient.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer(
      (_) async => jsonResponse({
        'items': [
          {
            'name': 'Bread',
            'quantity': 1,
            'unit': 'units',
            'confidence': 0.8,
            'food_group': 'carbohydrates',
          },
        ],
      }),
    );

    final notifier = container.read(describeReceiptControllerProvider.notifier);
    await notifier.describe('a loaf of bread');

    final state = container.read(describeReceiptControllerProvider);
    expect(state.hasError, isFalse);
    expect(state.value?.items.single.name, 'Bread');
  });

  test('parseShoppingDescriptionControllerProvider completes and lands its '
      'terminal state when only ref.read (never watched) — currently unwired '
      'to any screen, but must not regress once it is', () async {
    when(
      () => httpClient.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer(
      (_) async => jsonResponse({
        'items': [
          {
            'name': 'Tomatoes',
            'quantity': 4,
            'unit': 'units',
            'confidence': 0.7,
            'food_group': 'vegetables',
          },
        ],
        'clarifying_questions': <Object?>[],
      }),
    );

    final notifier = container.read(
      parseShoppingDescriptionControllerProvider.notifier,
    );
    await notifier.parse('4 tomatoes');

    final state = container.read(parseShoppingDescriptionControllerProvider);
    expect(state.hasError, isFalse);
    expect(state.value?.items.single.name, 'Tomatoes');
  });

  test('generateMealPlanControllerProvider completes and lands its terminal '
      'state when only ref.read (never watched)', () async {
    when(
      () => httpClient.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer(
      (_) async => jsonResponse({
        'suggestions': [
          {
            'recipe_id': 1,
            'title': 'Soup',
            'reason': 'Uses pantry staples',
            'missing_ingredients': <Object?>[],
          },
        ],
      }),
    );

    final notifier = container.read(
      generateMealPlanControllerProvider.notifier,
    );
    await notifier.generate(
      const MealPlanRequest(
        pantry: [],
        recipeHistory: [],
        foodGroupCoverage: {},
        purchaseTolerance: 0.5,
        mealsPerWeek: 3,
        dietaryFlags: [],
      ),
    );

    final state = container.read(generateMealPlanControllerProvider);
    expect(state.hasError, isFalse);
    expect(state.value?.suggestions.single.title, 'Soup');
  });

  test('importRecipeControllerProvider completes and lands its terminal state '
      'when only ref.read (never watched)', () async {
    when(
      () => httpClient.post(
        any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'),
      ),
    ).thenAnswer(
      (_) async => jsonResponse({
        'external_id': 'r1',
        'title': 'Imported',
        'ingredients': <Object?>[],
        'instructions': <Object?>[],
      }),
    );

    final notifier = container.read(importRecipeControllerProvider.notifier);
    await notifier.importFromUrl(
      const ImportUrlRequest(url: 'https://example.com/r'),
    );

    final state = container.read(importRecipeControllerProvider);
    expect(state.hasError, isFalse);
    expect(state.value?.title, 'Imported');
  });
}
