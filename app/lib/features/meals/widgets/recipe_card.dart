import 'package:flutter/material.dart';
import 'package:glean/data/models/recipe_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

/// One row in the saved-recipe library list. Wrapped in `SwipeToDeleteRow`
/// by the caller (`MealsScreen`) — this widget only renders the card
/// content, keeping the delete affordance owned by exactly one place
/// (AC-UX-01).
class RecipeCard extends StatelessWidget {
  const RecipeCard({required this.recipe, required this.onTap, super.key});

  final RecipeView recipe;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final List<RecipeMetaItem> meta = getRecipeMeta(
      totalTimeMins: recipe.totalTimeMins,
      yieldCount: recipe.yieldCount,
      difficulty: recipe.difficulty,
    );
    final List<String> tags = getRecipeTags(
      cuisine: recipe.cuisine,
      dietaryFlags: recipe.dietaryFlags,
    );

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(tokens.radius.lg),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Expanded(
                    child: Text(
                      recipe.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
              if (meta.isNotEmpty) ...<Widget>[
                SizedBox(height: tokens.spacing.sm),
                Wrap(
                  spacing: 14,
                  runSpacing: 4,
                  children: <Widget>[
                    for (final RecipeMetaItem item in meta)
                      _MetaChip(item: item),
                  ],
                ),
              ],
              if (tags.isNotEmpty) ...<Widget>[
                SizedBox(height: tokens.spacing.sm),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: <Widget>[
                    for (final String tag in tags) GleanBadge(label: tag),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({required this.item});

  final RecipeMetaItem item;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        Icon(item.icon, size: 14, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 4),
        Text(item.label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
