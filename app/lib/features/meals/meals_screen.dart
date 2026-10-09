/// The Meals tab: a deliberately curated recipe library (Saved) plus one
/// real inline search affordance (Search) — FLUTTER_MIGRATION.md §6 "Meals".
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/data/providers/recipes_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import 'actions.dart';
import 'widgets/meals_search_panel.dart';
import 'widgets/meals_states.dart';
import 'widgets/recipe_card.dart';

enum MealsTab { saved, search }

class MealsScreen extends ConsumerStatefulWidget {
  const MealsScreen({super.key});

  @override
  ConsumerState<MealsScreen> createState() => _MealsScreenState();
}

class _MealsScreenState extends ConsumerState<MealsScreen> {
  MealsTab _tab = MealsTab.saved;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final AsyncValue<List<RecipeView>> savedAsync = ref.watch(
      savedRecipesProvider,
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Meals')),
      body: Padding(
        padding: EdgeInsets.all(tokens.spacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            SegmentedButton<MealsTab>(
              segments: <ButtonSegment<MealsTab>>[
                ButtonSegment<MealsTab>(
                  value: MealsTab.saved,
                  label: Text('Saved (${savedAsync.value?.length ?? 0})'),
                  icon: const Icon(Icons.bookmark_rounded),
                ),
                const ButtonSegment<MealsTab>(
                  value: MealsTab.search,
                  label: Text('Search'),
                  icon: Icon(Icons.search_rounded),
                ),
              ],
              selected: <MealsTab>{_tab},
              onSelectionChanged: (Set<MealsTab> selection) {
                ref.read(hapticsProvider).selectionClick();
                setState(() => _tab = selection.first);
              },
            ),
            SizedBox(height: tokens.spacing.lg),
            Expanded(
              child: _tab == MealsTab.search
                  ? const MealsSearchPanel()
                  : _SavedRecipesList(savedAsync: savedAsync),
            ),
          ],
        ),
      ),
    );
  }
}

class _SavedRecipesList extends ConsumerWidget {
  const _SavedRecipesList({required this.savedAsync});

  final AsyncValue<List<RecipeView>> savedAsync;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      child: KeyedSubtree(
        key: ValueKey<bool>(!savedAsync.hasValue),
        child: !savedAsync.hasValue
            ? const ListSkeleton(rows: 4, rowHeight: 96)
            : savedAsync.maybeWhen(
                data: (List<RecipeView> recipes) {
                  if (recipes.isEmpty) {
                    return const MealsMessagePanel(
                      icon: Icons.restaurant_rounded,
                      title: 'No saved recipes',
                      message: 'Search for recipes or import one from a URL.',
                    );
                  }
                  // No AnimatedList: a SwipeToDeleteRow's Dismissible already
                  // animates its own removal gap closed.
                  return ListView(
                    children: <Widget>[
                      for (int i = 0; i < recipes.length; i++) ...<Widget>[
                        if (i > 0) const SizedBox(height: 12),
                        SwipeToDeleteRow(
                          key: ValueKey<int>(recipes[i].id),
                          dismissibleKey: ValueKey<int>(recipes[i].id),
                          onDelete: () =>
                              deleteRecipeWithUndo(context, ref, recipes[i]),
                          child: RecipeCard(
                            recipe: recipes[i],
                            onTap: () {
                              ref.read(hapticsProvider).lightImpact();
                              context.pushNamed(
                                AppRoutes.mealsDetail.name,
                                pathParameters: <String, String>{
                                  'id': '${recipes[i].id}',
                                },
                              );
                            },
                          ),
                        ),
                      ],
                    ],
                  );
                },
                orElse: () => const MealsMessagePanel(
                  icon: Icons.error_outline_rounded,
                  title: 'Could not load your recipes',
                  message: 'Check your connection and try again.',
                ),
              ),
      ),
    );
  }
}
