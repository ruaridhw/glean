// Saved-recipe-library reads for the current user. Backend recipe search is a remote command provider,
// not a local read.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/recipe_view.dart';
import 'database_providers.dart';
import 'repository_providers.dart';

final StreamProvider<List<RecipeView>> savedRecipesProvider =
    StreamProvider<List<RecipeView>>((ref) {
      final userId = ref.watch(currentUserIdProvider);
      return ref.watch(recipesRepositoryProvider).watchSaved(userId);
    });
