import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/recipes.dart';
import '../text_input.dart';
import 'api_providers.dart';

/// How long to wait after the last keystroke before actually issuing the
/// search request.
const Duration recipeSearchDebounce = Duration(milliseconds: 350);

/// Debounced recipe search — the only endpoint that wants query-style
/// caching (FLUTTER_MIGRATION.md §3, AC-DATA-08).
///
/// `family` keys each in-flight search by its raw query text; `autoDispose`
/// is what makes debouncing work without a separate timer/cancel-token
/// abstraction: when the UI moves on to a new keystroke, the *previous*
/// family instance loses its last listener and Riverpod tears it down. If
/// that happens before its `Future.delayed` below elapses, `ref.mounted`
/// is false when execution resumes and the network call is never issued —
/// so rapid typing produces exactly one request (for whichever query the
/// user stopped on long enough), not one per keystroke. This is not request
/// *cancellation* (a Dart `Future` can't be cancelled once started); it's
/// debouncing the point at which the request is issued in the first place.
// No explicit type annotation: `FutureProviderFamily` is only exported from
// `package:riverpod/misc.dart`, not the `flutter_riverpod` barrel this file
// otherwise relies on, and pubspec.yaml (orchestrator-owned) declares only
// `flutter_riverpod`. Letting Dart infer the type avoids an
// `depend_on_referenced_packages` lint on a package we don't declare.
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
    });

/// Recipe detail lookup by external id (`GET /recipes/{id}`). `family` +
/// `autoDispose` so a screen that navigates away drops the fetch rather
/// than holding it cached forever — recipe detail isn't the query-caching
/// case AC-DATA-08 calls out (that's search only).
final recipeDetailProvider = FutureProvider.autoDispose
    .family<RecipeOut, String>((ref, recipeId) async {
      final client = ref.watch(apiClientProvider);
      return client.getRecipe(recipeId);
    });

/// Command controller for `POST /recipes/import-url`. The imported recipe
/// is an ephemeral proposal (AC-DATA-06): the caller still has to run it
/// through the DATA module's save/dedupe mutation (AC-MEAL-10 — import
/// dedupes and says "already saved") for it to become a persisted recipe.
class ImportRecipeController extends AsyncNotifier<RecipeOut?> {
  @override
  FutureOr<RecipeOut?> build() => null;

  /// See `ScanReceiptController.scan`'s doc comment
  /// (`lib/api/providers/receipts_providers.dart`) for why the
  /// [Ref.keepAlive] hold-and-release is here (FINDINGS.md F-15). Callers no
  /// longer need their own keep-alive workaround for this reason — see
  /// `lib/features/meals/meals_import_screen.dart`.
  Future<void> importFromUrl(ImportUrlRequest request) async {
    state = const AsyncLoading();
    final keepAliveLink = ref.keepAlive();
    try {
      final client = ref.read(apiClientProvider);
      state = await AsyncValue.guard(() => client.importRecipeFromUrl(request));
    } finally {
      keepAliveLink.close();
    }
  }
}

final AsyncNotifierProvider<ImportRecipeController, RecipeOut?>
importRecipeControllerProvider = AsyncNotifierProvider.autoDispose(
  ImportRecipeController.new,
);
