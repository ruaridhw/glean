/// A search result **preview** — AC-MEAL-01: tapping a search result opens
/// this, and nothing is persisted until the user explicitly taps the
/// bookmark. Pushed with a plain `Navigator.push`/`MaterialPageRoute`
/// (deliberately *not* a `go_router` route): a preview is ephemeral and not
/// deep-linkable, so it needs no place in the route table, and `MealsScreen`
/// (the only place that pushes this) already dedupes against the saved
/// library before ever reaching here — see its `_onResultTap`.
///
/// Once saved, this screen simply *becomes* [SavedRecipeDetail] in place —
/// there is exactly one implementation of "what a saved recipe looks like",
/// reused by both this screen and the `go_router`-routed
/// `MealDetailScreen`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/design_system/design_system.dart';

import 'actions.dart';
import 'presentation.dart';
import 'saved_recipe_detail.dart';
import 'widgets/meals_skeletons.dart';
import 'widgets/recipe_detail_view.dart';

class RecipePreviewScreen extends ConsumerStatefulWidget {
  const RecipePreviewScreen({required this.externalId, super.key});

  final String externalId;

  @override
  ConsumerState<RecipePreviewScreen> createState() =>
      _RecipePreviewScreenState();
}

class _RecipePreviewScreenState extends ConsumerState<RecipePreviewScreen> {
  int? _savedRecipeId;
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    // Once saved, this screen *is* the saved detail screen — no navigation,
    // just swapping which widget this route builds (AC-MEAL-02/08).
    final int? savedId = _savedRecipeId;
    if (savedId != null) {
      return SavedRecipeDetail(recipeId: savedId);
    }

    final AsyncValue<RecipeOut> detailAsync = ref.watch(
      recipeDetailProvider(widget.externalId),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(detailAsync.value?.title ?? 'Recipe'),
        actions: <Widget>[
          IconButton(
            icon: _saving
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.bookmark_border_rounded),
            tooltip: 'Save recipe',
            onPressed: (_saving || !detailAsync.hasValue)
                ? null
                : () => _onSave(detailAsync.requireValue),
          ),
        ],
      ),
      body: GleanCrossFade(
        showSkeleton: !detailAsync.hasValue && !detailAsync.hasError,
        skeleton: const RecipeDetailSkeleton(),
        content: detailAsync.when(
          data: (RecipeOut detail) => SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: RecipeDetailView(data: RecipeDetailData.fromApi(detail)),
          ),
          // A cold-start-deep-link-style dead end doesn't apply here (this
          // screen is only ever reached by tapping a live search result,
          // never a deep link), so a plain in-body message plus the app
          // bar's own back button — not `RouteErrorScreen` — is the right
          // recovery affordance.
          error: (Object error, StackTrace stackTrace) => Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                'Could not load this recipe. Go back and try again.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          ),
          loading: () => const SizedBox.shrink(),
        ),
      ),
    );
  }

  Future<void> _onSave(RecipeOut detail) async {
    setState(() => _saving = true);
    ref.read(hapticsProvider).mediumImpact(); // data commit (AC-HAP-05).
    try {
      final int id = await saveApiRecipe(ref, detail);
      if (!mounted) return;
      GleanSnackBar.show(context, 'Recipe saved');
      setState(() {
        _savedRecipeId = id;
        _saving = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      GleanSnackBar.show(context, 'Could not save this recipe. Try again.');
    }
  }
}
