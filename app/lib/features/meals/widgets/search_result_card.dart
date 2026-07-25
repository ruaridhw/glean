import 'package:flutter/material.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/design_system/design_system.dart';

/// One row in the live search results list. Tapping it previews the recipe
/// (AC-MEAL-01) — it never persists anything by itself; that is entirely the
/// caller's (`MealsScreen`) job.
class SearchResultCard extends StatelessWidget {
  const SearchResultCard({
    required this.result,
    required this.onTap,
    super.key,
  });

  final RecipeSearchResult result;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
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
                      result.title,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ],
              ),
              SizedBox(height: tokens.spacing.sm),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: <Widget>[
                  if (result.cuisine != null)
                    GleanBadge(label: result.cuisine!),
                  if (result.difficulty != null)
                    GleanBadge(label: result.difficulty!),
                  if (result.totalTimeMins != null)
                    GleanBadge(label: '${result.totalTimeMins} min'),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
