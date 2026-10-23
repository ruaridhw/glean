/// Cards for the proposal review: a meal the generation suggested, and a meal already in the week that the
/// planner offered an alternative for. Both put Swap on the card and open their panel in place, with the
/// panel's buttons on one row at the bottom (V3 direction A).
library;

import 'package:flutter/material.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/design_system/design_system.dart';

/// The attribute labels' place are reserved from V3; recipe attributes arrive with V5. Until then the row is
/// three deliberately empty dashed chips. They carry no invented value, and the semantics say so once.
class ProposalAttributePlaceholders extends StatelessWidget {
  const ProposalAttributePlaceholders({super.key});

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Semantics(
      label: 'Recipe details not available yet',
      child: ExcludeSemantics(
        child: Wrap(
          spacing: context.tokens.spacing.xs,
          runSpacing: context.tokens.spacing.xs,
          children: <Widget>[
            for (int i = 0; i < 3; i++)
              Container(
                width: 44,
                height: 22,
                decoration: BoxDecoration(
                  border: Border.all(color: colorScheme.outlineVariant),
                  borderRadius: BorderRadius.circular(context.tokens.radius.sm),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Open swap panel for a new meal: the server's one alternative, taken in place. "Find another" is V10 and is
/// deliberately absent, so no note field or second button is offered yet.
class ProposalSwapPanel extends StatelessWidget {
  const ProposalSwapPanel({
    super.key,
    required this.alternative,
    required this.onUseAlternative,
  });

  final MealPlanRecipe alternative;
  final VoidCallback onUseAlternative;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Container(
      margin: EdgeInsets.only(top: tokens.spacing.sm),
      padding: EdgeInsets.all(tokens.spacing.md),
      decoration: BoxDecoration(
        border: Border.all(color: colorScheme.outline, width: 2),
        borderRadius: BorderRadius.circular(tokens.radius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Alternative: ${alternative.title}',
            style: textTheme.titleSmall,
          ),
          if (alternative.reason.isNotEmpty) ...<Widget>[
            SizedBox(height: tokens.spacing.xs),
            Text(
              alternative.reason,
              style: textTheme.bodySmall?.copyWith(
                color: colorScheme.onSurfaceVariant,
              ),
            ),
          ],
          SizedBox(height: tokens.spacing.sm),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              OutlinedButton(
                onPressed: onUseAlternative,
                child: const Text('Use alternative'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// One suggested meal. [meal] is what the card currently shows (the original or a swapped alternative);
/// [alternative] is the server's alternative for the original, which is what Swap offers.
class ProposalMealCard extends StatelessWidget {
  const ProposalMealCard({
    super.key,
    required this.meal,
    required this.alternative,
    required this.swapped,
    required this.swapOpen,
    required this.onToggleSwap,
    required this.onUseAlternative,
  });

  final MealPlanRecipe meal;
  final MealPlanRecipe? alternative;
  final bool swapped;
  final bool swapOpen;
  final VoidCallback onToggleSwap;
  final VoidCallback onUseAlternative;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Expanded(child: Text(meal.title, style: textTheme.titleMedium)),
                if (alternative != null)
                  TextButton(
                    onPressed: onToggleSwap,
                    child: Text(swapped ? 'Swap back' : 'Swap'),
                  ),
              ],
            ),
            SizedBox(height: tokens.spacing.xs),
            const ProposalAttributePlaceholders(),
            if (meal.reason.isNotEmpty) ...<Widget>[
              SizedBox(height: tokens.spacing.sm),
              Text(
                meal.reason,
                style: textTheme.bodyMedium?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
            if (swapOpen && alternative != null)
              ProposalSwapPanel(
                alternative: alternative!,
                onUseAlternative: onUseAlternative,
              ),
          ],
        ),
      ),
    );
  }
}

/// A meal already in the week: greyed, tagged, and swappable through `planned_alternatives`. Generation never
/// replaces it on its own (ADR 0020); only the user's own swap, saved with Add to plan, changes the entry.
class ProposalPlannedCard extends StatelessWidget {
  const ProposalPlannedCard({
    super.key,
    required this.title,
    required this.alternative,
    required this.swapped,
    required this.swapOpen,
    required this.onToggleSwap,
    required this.onUseAlternative,
  });

  final String title;
  final MealPlanRecipe? alternative;
  final bool swapped;
  final bool swapOpen;
  final VoidCallback onToggleSwap;
  final VoidCallback onUseAlternative;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Opacity(
      opacity: 0.55,
      child: Card(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Expanded(child: Text(title, style: textTheme.titleMedium)),
                  if (alternative != null)
                    TextButton(
                      onPressed: onToggleSwap,
                      child: Text(swapped ? 'Swap back' : 'Swap'),
                    ),
                ],
              ),
              SizedBox(height: tokens.spacing.xs),
              Align(
                alignment: Alignment.centerLeft,
                child: Container(
                  padding: EdgeInsets.symmetric(
                    horizontal: tokens.spacing.sm,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    border: Border.all(color: colorScheme.outline),
                    borderRadius: BorderRadius.circular(tokens.radius.sm),
                  ),
                  child: Text('already planned', style: textTheme.labelSmall),
                ),
              ),
              if (swapOpen && alternative != null)
                ProposalSwapPanel(
                  alternative: alternative!,
                  onUseAlternative: onUseAlternative,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
