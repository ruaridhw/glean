/// Cards for the proposal review: a meal the generation suggested, and a meal already in the week that the
/// planner offered an alternative for. Both put Swap on the card and open their panel in place, with the
/// panel's buttons on one row at the bottom (V3 direction A).
library;

import 'package:flutter/material.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/design_system/design_system.dart';

import '../proposal_labels.dart';

/// What a meal is: protein, carb, dish type and hands-on time, as V3's design places them (direction A,
/// "fish · rice · traybake · 20 min"). The values are measured by V5's enrichment; a meal with nothing measured
/// yet, or nothing the model was sure enough about, gets no row at all rather than an empty chip or a guess.
class ProposalAttributeLabels extends StatelessWidget {
  const ProposalAttributeLabels({super.key, required this.attributes});

  final MealPlanAttributes? attributes;

  @override
  Widget build(BuildContext context) {
    final List<String> labels = proposalLabels(attributes);
    if (labels.isEmpty) {
      return const SizedBox.shrink();
    }
    return Wrap(
      spacing: context.tokens.spacing.xs,
      runSpacing: context.tokens.spacing.xs,
      children: <Widget>[
        for (final String label in labels) GleanBadge(label: label),
      ],
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
          if (proposalLabels(alternative.attributes).isNotEmpty) ...<Widget>[
            SizedBox(height: tokens.spacing.xs),
            ProposalAttributeLabels(attributes: alternative.attributes),
          ],
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
          // Wrap constrains the button to the card's width, so a long label wraps instead of overflowing at
          // large text scales. The panel's actions stay on one row while they fit.
          Wrap(
            alignment: WrapAlignment.end,
            spacing: tokens.spacing.sm,
            runSpacing: tokens.spacing.sm,
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

/// The widest a card's Swap / Swap back button may be. Uncapped, "Swap back" at 2x text is wider than the space
/// beside the title on a 320 px screen and the title Row overflows; capped, its label wraps instead.
double _swapButtonMaxWidth(BuildContext context) =>
    MediaQuery.sizeOf(context).width * 0.4;

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
                  ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: _swapButtonMaxWidth(context),
                    ),
                    child: TextButton(
                      onPressed: onToggleSwap,
                      child: Text(swapped ? 'Swap back' : 'Swap'),
                    ),
                  ),
              ],
            ),
            if (proposalLabels(meal.attributes).isNotEmpty) ...<Widget>[
              SizedBox(height: tokens.spacing.xs),
              ProposalAttributeLabels(attributes: meal.attributes),
            ],
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
                    ConstrainedBox(
                      constraints: BoxConstraints(
                        maxWidth: _swapButtonMaxWidth(context),
                      ),
                      child: TextButton(
                        onPressed: onToggleSwap,
                        child: Text(swapped ? 'Swap back' : 'Swap'),
                      ),
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
