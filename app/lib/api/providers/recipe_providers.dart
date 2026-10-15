import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/recipes.dart';
import '../text_input.dart';
import 'api_providers.dart';

/// How long to wait after the last keystroke before actually issuing the
/// search request.
const Duration recipeSearchDebounce = Duration(milliseconds: 350);

/// Debounced recipe search. `autoDispose` makes the debounce work without a timer abstraction: when the UI moves
/// to a new keystroke the previous family instance loses its last listener and is torn down; if that happens
/// before its `Future.delayed` elapses, `ref.mounted` is false and the request is never issued. This debounces
/// when the request is issued; it does not cancel one in flight.
// No explicit type annotation: `FutureProviderFamily` is only exported from `package:riverpod/misc.dart`, which
// pubspec.yaml doesn't declare; inferring avoids a `depend_on_referenced_packages` lint.
// Surface remote failures promptly. Riverpod's automatic retries otherwise
// keep auth rejections behind a loading skeleton instead of showing recovery.
final recipeSearchProvider = FutureProvider.autoDispose
    .family<RecipeSearchResponse, String>((ref, rawQuery) async {
      final query = toRequiredSubmittedText(rawQuery);
      if (query == null) {
        return const RecipeSearchResponse(results: [], total: 0);
      }

      await Future<void>.delayed(recipeSearchDebounce);
      if (!ref.mounted) {
        return const RecipeSearchResponse(results: [], total: 0);
      }

      final client = ref.watch(apiClientProvider);
      return client.searchRecipes(q: query);
    }, retry: (retryCount, error) => null);

/// Recipe detail lookup by external id. `autoDispose` so a screen that navigates away drops the fetch rather
/// than caching it.
final recipeDetailProvider = FutureProvider.autoDispose
    .family<RecipeOut, String>((ref, recipeId) async {
      final client = ref.watch(apiClientProvider);
      return client.getRecipe(recipeId);
    }, retry: (retryCount, error) => null);
