import 'package:flutter/material.dart';

/// AC-MEAL-07: search is now a real inline input in the Meals tab's own
/// Search segment (see `MealsScreen`/`MealsSearchPanel`) — the separate
/// pushed search screen the RN app had is dropped, along with the fake
/// search pill that used to link to it.
///
/// This route (`/meals/search`) still exists in `router.dart`, which is
/// outside this module's remit (`lib/router/**`) to edit or remove; nothing
/// in this feature module navigates here any more. It is kept as a harmless,
/// honest dead end rather than the confusing alternative of silently
/// reusing this path for something else. See the final report's flagged
/// follow-up: the router module should prune this route (and the two
/// `test/router/*.dart` cases that assert on its placeholder text) once this
/// wave lands.
class MealsSearchScreen extends StatelessWidget {
  const MealsSearchScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Search recipes')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            'Search now lives in the Meals tab.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
      ),
    );
  }
}
