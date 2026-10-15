/// A search result preview: nothing is persisted until the user taps the bookmark. Pushed with a plain
/// `Navigator.push` rather than a `go_router` route, since a preview is ephemeral and not deep-linkable;
/// `MealsScreen` already dedupes against the saved library before pushing it (see `_onResultTap`). Once saved,
/// this screen becomes [SavedRecipeDetail] in place.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/recipe_providers.dart';
import 'package:glean/design_system/design_system.dart';

import 'actions.dart';
import 'presentation.dart';
import 'saved_recipe_detail.dart';
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
    // Once saved, this screen is the saved detail screen: swap which widget this route builds, no navigation.
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
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 220),
        child: KeyedSubtree(
          key: ValueKey<bool>(!detailAsync.hasValue && !detailAsync.hasError),
          child: !detailAsync.hasValue && !detailAsync.hasError
              ? const ListSkeleton(rows: 3, rowHeight: 160, headerHeight: 96)
              : detailAsync.when(
                  data: (RecipeOut detail) => SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: RecipeDetailView(
                      data: RecipeDetailData.fromApi(detail),
                    ),
                  ),
                  // This screen is only reached from a live search result, never a deep link, so a plain in-body message plus the
                  // app bar's back button is the right recovery, not `RouteErrorScreen`.
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
      ),
    );
  }

  Future<void> _onSave(RecipeOut detail) async {
    setState(() => _saving = true);
    ref.read(hapticsProvider).mediumImpact(); // data commit.
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
