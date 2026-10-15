// Saved-recipe-library reads for the current user. Recipe *search* against
// the backend is a remote command provider, not a local read — it belongs
// to the API module (FLUTTER_MIGRATION.md §3: only local drift reads live
// here).
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/recipe_view.dart';
import 'database_providers.dart';
import 'repository_providers.dart';

final StreamProvider<List<RecipeView>> savedRecipesProvider =
    StreamProvider<List<RecipeView>>((ref) {
      final userId = ref.watch(currentUserIdProvider);
      return ref.watch(recipesRepositoryProvider).watchSaved(userId);
    });
