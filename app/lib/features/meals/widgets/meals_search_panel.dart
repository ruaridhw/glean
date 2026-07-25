/// The Search segment's content: one real inline search input, live results,
/// empty/no-results/error states, and the import-from-URL affordance
/// (AC-MEAL-07/10). Replaces the RN app's fake search pill *and* its
/// separate pushed search screen — there is exactly one search affordance.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import '../presentation.dart';
import '../recipe_preview_screen.dart';
import 'meals_states.dart';
import 'meals_skeletons.dart';
import 'search_result_card.dart';

class MealsSearchPanel extends ConsumerStatefulWidget {
  const MealsSearchPanel({super.key});

  @override
  ConsumerState<MealsSearchPanel> createState() => _MealsSearchPanelState();
}

class _MealsSearchPanelState extends ConsumerState<MealsSearchPanel> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _controller.addListener(_onQueryChanged);
  }

  @override
  void dispose() {
    _controller.removeListener(_onQueryChanged);
    _controller.dispose();
    super.dispose();
  }

  void _onQueryChanged() => setState(() {});

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final String query = _controller.text.trim();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Row(
          children: <Widget>[
            Expanded(
              child: TextField(
                controller: _controller,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  hintText: 'Search recipes…',
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: query.isEmpty
                      ? null
                      : IconButton(
                          icon: const Icon(Icons.close_rounded),
                          onPressed: _controller.clear,
                        ),
                ),
              ),
            ),
            SizedBox(width: tokens.spacing.sm),
            IconButton(
              icon: const Icon(Icons.link_rounded),
              tooltip: 'Import recipe from a URL',
              onPressed: () => context.pushNamed(AppRoutes.mealsImport.name),
            ),
          ],
        ),
        SizedBox(height: tokens.spacing.lg),
        Expanded(
          child: query.isEmpty
              ? const MealsMessagePanel(
                  icon: Icons.search_rounded,
                  title: 'Search recipes',
                  message:
                      'Find new meals to add to your library, or '
                      'import one from a link.',
                )
              : _SearchResults(query: query),
        ),
      ],
    );
  }
}

class _SearchResults extends ConsumerWidget {
  const _SearchResults({required this.query});

  final String query;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<RecipeSearchResponse> resultsAsync = ref.watch(
      recipeSearchProvider(query),
    );

    // AC-TRN-01: skeleton → content cross-fades everywhere, including a
    // live search re-querying as the user keeps typing — never a hard cut.
    return GleanCrossFade(
      showSkeleton: resultsAsync.isLoading,
      skeleton: const RecipeListSkeleton(),
      content: resultsAsync.when(
        loading: () => const SizedBox.shrink(),
        error: (Object error, StackTrace stackTrace) => MealsMessagePanel(
          icon: Icons.error_outline_rounded,
          title: 'Search failed',
          message: describeRecipeSearchError(error),
        ),
        data: (RecipeSearchResponse response) {
          if (response.results.isEmpty) {
            return MealsMessagePanel(
              icon: Icons.search_off_rounded,
              title: 'No recipes found',
              message: 'No results for "$query". Try a different search.',
            );
          }
          return ListView.separated(
            itemCount: response.results.length,
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (BuildContext context, int index) {
              final RecipeSearchResult result = response.results[index];
              return SearchResultCard(
                result: result,
                onTap: () => _onResultTap(context, ref, result),
              );
            },
          );
        },
      ),
    );
  }

  /// AC-MEAL-01: preview, don't save. If this result is already in the
  /// user's library (matched by `external_id`, the same dedupe key search
  /// always used), go straight to the real saved detail and say so
  /// (AC-MEAL-10) rather than opening a redundant "unsaved" preview of
  /// something already curated.
  Future<void> _onResultTap(
    BuildContext context,
    WidgetRef ref,
    RecipeSearchResult result,
  ) async {
    ref.read(hapticsProvider).lightImpact();
    final existing = await ref
        .read(recipesRepositoryProvider)
        .getByExternalId(
          externalId: result.externalId,
          userId: ref.read(currentUserIdProvider),
        );
    if (!context.mounted) return;

    if (existing != null) {
      GleanSnackBar.show(context, 'Already saved');
      unawaited(
        context.pushNamed(
          AppRoutes.mealsDetail.name,
          pathParameters: <String, String>{'id': '${existing.id}'},
        ),
      );
      return;
    }

    unawaited(
      Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) => RecipePreviewScreen(externalId: result.externalId),
        ),
      ),
    );
  }
}
