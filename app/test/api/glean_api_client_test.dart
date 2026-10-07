import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/api_client.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/text_input.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

class MockHttpClient extends Mock implements http.Client {}

void main() {
  late MockHttpClient httpClient;
  late GleanApiClient client;

  http.Response jsonResponse(Object? body, {int statusCode = 200}) {
    return http.Response(
      body == null ? '' : jsonEncode(body),
      statusCode,
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
    client = GleanApiClient(
      baseUrl: 'http://localhost:8000',
      httpClient: httpClient,
      accessTokenProvider: () async => 'test-token',
      timeout: const Duration(seconds: 5),
    );
  });

  group('recipes', () {
    test(
      'searchRecipes serialises query params and deserialises results',
      () async {
        when(
          () => httpClient.get(any(), headers: any(named: 'headers')),
        ).thenAnswer(
          (_) async => jsonResponse({
            'results': [
              {
                'external_id': 'r1',
                'title': 'Soup',
                'cuisine': 'french',
                'difficulty': 'easy',
                'total_time_mins': 30,
                'dietary_flags': ['vegan'],
              },
            ],
            'total': 1,
          }),
        );

        final result = await client.searchRecipes(
          q: 'soup',
          page: 2,
          perPage: 10,
        );

        final requestUri =
            verify(
                  () => httpClient.get(
                    captureAny(),
                    headers: captureAny(named: 'headers'),
                  ),
                ).captured.first
                as Uri;
        expect(requestUri.path, '/recipes/search');
        expect(requestUri.queryParameters['q'], 'soup');
        expect(requestUri.queryParameters['page'], '2');
        expect(requestUri.queryParameters['per_page'], '10');

        expect(result.total, 1);
        expect(result.results.single.externalId, 'r1');
        expect(result.results.single.dietaryFlags, ['vegan']);
      },
    );

    test('getRecipe deserialises not_suitable_for and source_url', () async {
      when(
        () => httpClient.get(any(), headers: any(named: 'headers')),
      ).thenAnswer(
        (_) async => jsonResponse({
          'external_id': 'r1',
          'title': 'Peanut satay',
          'source_url': 'https://example.com/satay',
          'not_suitable_for': ['peanut allergy'],
          'ingredients': <Object?>[],
          'instructions': <Object?>[],
        }),
      );

      final recipe = await client.getRecipe('r1');

      expect(recipe.sourceUrl, 'https://example.com/satay');
      expect(recipe.notSuitableFor, ['peanut allergy']);
    });

    test('importRecipeFromUrl serialises the request body', () async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => jsonResponse({
          'external_id': 'r2',
          'title': 'Imported',
          'ingredients': <Object?>[],
          'instructions': <Object?>[],
        }),
      );

      await client.importRecipeFromUrl(
        const ImportUrlRequest(url: 'https://example.com/r'),
      );

      final sentBody =
          verify(
                () => httpClient.post(
                  any(),
                  headers: any(named: 'headers'),
                  body: captureAny(named: 'body'),
                ),
              ).captured.single
              as String;
      final decoded = jsonDecode(sentBody) as Map<String, dynamic>;
      expect(decoded['url'], 'https://example.com/r');
    });
  });

  group('meal plan', () {
    test(
      'generateMealPlan sends non-empty food_groups/food_group_coverage',
      () async {
        when(
          () => httpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        ).thenAnswer((_) async => jsonResponse({'suggestions': <Object?>[]}));

        final request = MealPlanRequest(
          pantry: const [
            CompressedPantryItem(
              id: 1,
              name: 'Chicken thighs',
              quantity: 500,
              unit: 'g',
              foodGroup: 'protein',
              urgencyScore: 42.5,
            ),
          ],
          recipeHistory: [
            RecipeHistoryItem(
              recipeId: 7,
              title: 'Curry',
              lastCookedAt: DateTime.utc(2026, 1, 1),
              foodGroups: const ['protein', 'veg'],
            ),
          ],
          foodGroupCoverage: const {'protein': 2, 'veg': 1},
          purchaseTolerance: 0.5,
          mealsPerWeek: 3,
          dietaryFlags: const ['vegetarian'],
          maxActiveTimeMins: 45,
        );

        final response = await client.generateMealPlan(request);

        final sentBody =
            verify(
                  () => httpClient.post(
                    any(),
                    headers: any(named: 'headers'),
                    body: captureAny(named: 'body'),
                  ),
                ).captured.single
                as String;
        final decoded = jsonDecode(sentBody) as Map<String, dynamic>;

        // AC-PLAN-08: the RN client hardcoded these empty, permanently
        // disabling the backend's food-group-balancing prompt rule.
        expect(decoded['food_group_coverage'], {'protein': 2, 'veg': 1});
        final historyItem =
            (decoded['recipe_history'] as List<dynamic>).single
                as Map<String, dynamic>;
        expect(historyItem['food_groups'], ['protein', 'veg']);
        expect(response.suggestions, isEmpty);
      },
    );
  });

  group('receipts', () {
    test(
      'scanReceipt sends a multipart request and parses category/food_group per item',
      () async {
        when(() => httpClient.send(any())).thenAnswer((invocation) async {
          final request = invocation.positionalArguments.single as http.Request;
          // Sanity-check the multipart envelope actually carries the image
          // bytes and a boundary consistent with its own Content-Type header.
          expect(
            request.headers['content-type'],
            contains('multipart/form-data; boundary='),
          );
          expect(request.headers['authorization'], 'Bearer test-token');
          expect(
            utf8.decode(request.bodyBytes, allowMalformed: true),
            contains('name="file"'),
          );

          final body = jsonEncode({
            'items': [
              {
                'name': 'Milk',
                'quantity': 1,
                'unit': 'l',
                'unit_price': 1.2,
                'confidence': 0.9,
                'category': 'dairy',
                'food_group': 'dairy',
              },
            ],
          });
          return http.StreamedResponse(
            Stream.value(utf8.encode(body)),
            200,
            headers: {'content-type': 'application/json'},
          );
        });

        final result = await client.scanReceipt(Uint8List.fromList([1, 2, 3]));

        expect(result.items.single.name, 'Milk');
        // AC-BE-04 / AC-DATA-11: food_group is carried through, not dropped.
        expect(result.items.single.category, 'dairy');
        expect(result.items.single.foodGroup, 'dairy');
      },
    );

    test(
      'describeReceipt trims text before sending and rejects blank input',
      () async {
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
                'category': 'bread',
                'food_group': 'carbohydrates',
              },
            ],
          }),
        );

        await client.describeReceipt('  milk\n  sourdough bread  \t');

        final sentBody =
            verify(
                  () => httpClient.post(
                    any(),
                    headers: any(named: 'headers'),
                    body: captureAny(named: 'body'),
                  ),
                ).captured.single
                as String;
        expect(jsonDecode(sentBody), {'text': 'milk\n  sourdough bread'});

        await expectLater(
          () => client.describeReceipt('   '),
          throwsA(isA<EmptyTextInputException>()),
        );
        // The blank-input rejection happens before any network call.
        verifyNever(
          () => httpClient.post(
            any(),
            headers: any(named: 'headers'),
            body: any(named: 'body'),
          ),
        );
      },
    );
  });

  group('shopping', () {
    test('parseShoppingDescription deserialises category, food_group and '
        'api_ingredient_id', () async {
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
              'category': 'nightshades',
              'food_group': 'vegetables',
              'api_ingredient_id': 'ing-123',
            },
          ],
          'clarifying_questions': ['Tinned or fresh?'],
        }),
      );

      final result = await client.parseShoppingDescription('4 tomatoes');

      final item = result.items.single;
      expect(item.category, 'nightshades');
      expect(item.foodGroup, 'vegetables');
      expect(item.apiIngredientId, 'ing-123');
      expect(result.clarifyingQuestions, ['Tinned or fresh?']);
    });

    test('a null category with food_group "other" parses fine — the real '
        'shape of the out-of-taxonomy fallback path', () async {
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
              'name': 'Mystery sauce',
              'quantity': 1,
              'unit': 'bottle',
              'confidence': 0.4,
              'category': null,
              'food_group': 'other',
            },
          ],
          'clarifying_questions': <Object?>[],
        }),
      );

      final result = await client.parseShoppingDescription('some sauce');

      final item = result.items.single;
      expect(item.category, isNull);
      expect(item.foodGroup, 'other');
    });
  });

  group('error handling', () {
    test(
      'a request exceeding the timeout throws ApiTimeoutException',
      () async {
        final timeoutClient = GleanApiClient(
          baseUrl: 'http://localhost:8000',
          httpClient: httpClient,
          timeout: const Duration(milliseconds: 20),
        );
        final neverCompletes = Completer<http.Response>();
        when(
          () => httpClient.get(any(), headers: any(named: 'headers')),
        ).thenAnswer((_) => neverCompletes.future);

        await expectLater(
          timeoutClient.searchRecipes(),
          throwsA(isA<ApiTimeoutException>()),
        );
      },
    );

    test('a 401 response throws ApiAuthException', () async {
      when(
        () => httpClient.get(any(), headers: any(named: 'headers')),
      ).thenAnswer(
        (_) async => jsonResponse({'detail': 'Missing token'}, statusCode: 401),
      );

      await expectLater(
        client.searchRecipes(),
        throwsA(
          isA<ApiAuthException>()
              .having((e) => e.statusCode, 'statusCode', 401)
              .having((e) => e.message, 'message', 'Missing token'),
        ),
      );
    });

    test('a 422 response throws ApiValidationException', () async {
      when(
        () => httpClient.post(
          any(),
          headers: any(named: 'headers'),
          body: any(named: 'body'),
        ),
      ).thenAnswer(
        (_) async => jsonResponse({
          'detail': [
            {
              'loc': ['body', 'meals_per_week'],
              'msg': 'Input should be greater than or equal to 1',
            },
          ],
        }, statusCode: 422),
      );

      await expectLater(
        client.generateMealPlan(
          const MealPlanRequest(
            pantry: [],
            recipeHistory: [],
            foodGroupCoverage: {},
            purchaseTolerance: 0.5,
            mealsPerWeek: 0,
            dietaryFlags: [],
          ),
        ),
        throwsA(isA<ApiValidationException>()),
      );
    });

    test(
      'a malformed body throws ApiParseException rather than crashing',
      () async {
        when(
          () => httpClient.get(any(), headers: any(named: 'headers')),
        ).thenAnswer((_) async => http.Response('not valid json', 200));

        await expectLater(
          client.searchRecipes(),
          throwsA(isA<ApiParseException>()),
        );
      },
    );

    test(
      'a parsed ingredient missing category parses fine — category is '
      'nullable, matching the backend\'s own out-of-taxonomy fallback',
      () async {
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
                'name': 'Mystery item',
                'quantity': 1,
                'unit': 'units',
                'confidence': 0.5,
                'food_group': 'other',
              },
            ],
          }),
        );

        final result = await client.describeReceipt('mystery item');

        expect(result.items.single.category, isNull);
        expect(result.items.single.foodGroup, 'other');
      },
    );

    test('a parsed ingredient missing food_group throws ApiParseException — '
        'receipt proposals always emit this computed field, unlike nullable meal-plan inputs '
        '(AC-DATA-11)', () async {
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
              'name': 'Mystery item',
              'quantity': 1,
              'unit': 'units',
              'confidence': 0.5,
              'category': 'dairy',
            },
          ],
        }),
      );

      await expectLater(
        client.describeReceipt('mystery item'),
        throwsA(isA<ApiParseException>()),
      );
    });

    test('a transport failure throws ApiNetworkException', () async {
      when(
        () => httpClient.get(any(), headers: any(named: 'headers')),
      ).thenThrow(Exception('Connection refused'));

      await expectLater(
        client.searchRecipes(),
        throwsA(isA<ApiNetworkException>()),
      );
    });
  });
}
