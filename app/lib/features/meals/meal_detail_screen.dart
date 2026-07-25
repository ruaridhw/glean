import 'package:flutter/material.dart';

/// Placeholder — the Meals feature wave replaces this wholesale.
///
/// [recipeId] arrives as a path parameter, not typed `extra` — a cold-start
/// deep link has no in-memory object to hand over, so it must be a plain
/// path segment the screen (or a provider it reads) resolves against the
/// database. The router already guards the format (non-numeric ids never
/// reach here — see `router.dart`'s redirect on this route); "valid id, no
/// such recipe" is a data lookup the Meals wave still needs to handle with
/// the same no-dead-end rule (AC-MEAL-12), reusing `RouteErrorScreen` rather
/// than calling `pop()` on a possibly-empty stack.
class MealDetailScreen extends StatelessWidget {
  const MealDetailScreen({required this.recipeId, super.key});

  final String recipeId;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Recipe')),
      body: Center(child: Text('Recipe $recipeId')),
    );
  }
}
