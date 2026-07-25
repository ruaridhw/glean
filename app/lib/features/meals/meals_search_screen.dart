import 'package:flutter/material.dart';

/// Placeholder — the Meals feature wave replaces this wholesale. Real
/// version is a single inline search input (AC-MEAL-07), not a separate
/// pushed screen with its own search box — but it still needs a route to
/// push to from within the Meals tab's own stack.
class MealsSearchScreen extends StatelessWidget {
  const MealsSearchScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Search recipes')),
      body: const Center(child: Text('Search recipes')),
    );
  }
}
