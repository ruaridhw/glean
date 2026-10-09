import 'package:flutter/material.dart';
import 'package:glean/router/route_error_screen.dart';

import 'saved_recipe_detail.dart';

/// The `go_router` entry point for `/meals/:id`: a saved recipe reached from the library list or a cold-start deep
/// link. [recipeId] arrives as a path parameter and the router already blocks a non-numeric id; "valid id, no such
/// recipe" is [SavedRecipeDetail]'s job. The parse guard below is defensive.
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
