import 'package:flutter/material.dart';

/// Placeholder — the Plan feature wave replaces this wholesale.
///
/// No incoming route params: unlike the RN app's `add_recipe_id` query
/// param (re-processed on every `useFocusEffect`, causing the duplicate
/// re-add bug — §11, AC-PLAN-11), "Add to plan" now stays on the recipe
/// screen and writes via a mutation provider directly (AC-MEAL-08/09). There
/// is nothing left for a route param to carry.
class PlanScreen extends StatelessWidget {
  const PlanScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Plan')),
      body: const Center(child: Text('Plan screen')),
    );
  }
}
