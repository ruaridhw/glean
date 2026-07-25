import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

class MockHttpClient extends Mock implements http.Client {}

void main() {
  setUpAll(() {
    registerFallbackValue(Uri.parse('http://localhost:8000/'));
  });

  test(
    'AC-DATA-08: recipeSearchProvider is a FutureProvider.family + autoDispose',
    () {
      // `.family` applied: calling it with an argument yields a concrete
      // FutureProvider for that query.
      expect(
        recipeSearchProvider('soup'),
        isA<FutureProvider<RecipeSearchResponse>>(),
      );
      // `.autoDispose` applied.
      expect(recipeSearchProvider.isAutoDispose, isTrue);
    },
  );

  test('debounced search: rapid input produces exactly one request', () async {
    final httpClient = MockHttpClient();
    var requestCount = 0;
    when(
      () => httpClient.get(any(), headers: any(named: 'headers')),
    ).thenAnswer((_) async {
      requestCount += 1;
      return http.Response(
        jsonEncode({'results': <Object?>[], 'total': 0}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });

    final container = ProviderContainer(
      overrides: [
        apiBaseUrlProvider.overrideWithValue('http://localhost:8000'),
        httpClientProvider.overrideWithValue(httpClient),
      ],
    );
    addTearDown(container.dispose);

    // Simulate rapid typing: each keystroke watches a new query and drops
    // the previous one before establishing the next — exactly what
    // `ref.watch(recipeSearchProvider(controller.text))` does on rebuild.
    ProviderSubscription<AsyncValue<RecipeSearchResponse>>? previous;
    for (final query in ['s', 'so', 'sou', 'soup']) {
      previous?.close();
      previous = container.listen(recipeSearchProvider(query), (_, _) {});
    }

    // Long enough for the debounce window on the final ('soup') query to
    // elapse, but the stale queries never get this far because they were
    // disposed (unwatched) well before their own debounce timer fired.
    await Future<void>.delayed(
      recipeSearchDebounce + const Duration(milliseconds: 150),
    );

    expect(requestCount, 1);
    previous?.close();
  });

  test('an empty query never issues a request', () async {
    final httpClient = MockHttpClient();
    when(
      () => httpClient.get(any(), headers: any(named: 'headers')),
    ).thenAnswer((_) async {
      return http.Response(
        jsonEncode({'results': <Object?>[], 'total': 0}),
        200,
        headers: {'content-type': 'application/json'},
      );
    });

    final container = ProviderContainer(
      overrides: [
        apiBaseUrlProvider.overrideWithValue('http://localhost:8000'),
        httpClientProvider.overrideWithValue(httpClient),
      ],
    );
    addTearDown(container.dispose);

    final result = await container.read(recipeSearchProvider('   ').future);

    expect(result.total, 0);
    verifyNever(() => httpClient.get(any(), headers: any(named: 'headers')));
  });
}
