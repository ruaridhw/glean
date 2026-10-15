import 'package:flutter/material.dart';
import 'package:glean/router/route_error_screen.dart';

import 'saved_recipe_detail.dart';

/// The `go_router` entry point for `/meals/:id` — a saved recipe reached
/// either from the library list or a cold-start deep link.
///
/// [recipeId] arrives as a path parameter, not typed `extra` (see the
/// router's own doc comment on this route): a cold-start deep link has no
/// in-memory object to hand over. The router already guards the format (a
/// non-numeric id never reaches here — see `router.dart`'s redirect on this
/// route); "valid id, no such recipe" is [SavedRecipeDetail]'s job
/// (AC-MEAL-12), which reuses [RouteErrorScreen] rather than calling `pop()`
/// on a possibly-empty stack. The parse guard below is defensive — belt and
/// braces against the same failure mode the router already blocks.
class MealDetailScreen extends StatelessWidget {
  const MealDetailScreen({required this.recipeId, super.key});

  final String recipeId;

  @override
  Widget build(BuildContext context) {
    final int? id = int.tryParse(recipeId);
    if (id == null) {
      return const RouteErrorScreen(message: 'This recipe could not be found.');
    }
    return SavedRecipeDetail(recipeId: id);
  }
}
