import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../presentation.dart';

/// The ingredients card — each row a formatted [IngredientLine] plus its
/// "in pantry"/"to buy" badge (AC-MEAL-11), hidden when pantry state is
/// unresolved (`line.inPantry == null`).
class IngredientsSection extends StatelessWidget {
  const IngredientsSection({required this.ingredients, super.key});

  final List<IngredientLine> ingredients;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        child: Column(
          children: <Widget>[
            for (int i = 0; i < ingredients.length; i++)
              Container(
                padding: const EdgeInsets.symmetric(vertical: 8),
                decoration: i < ingredients.length - 1
                    ? BoxDecoration(
                        border: Border(
                          bottom: BorderSide(
                            color: Theme.of(context).colorScheme.outline,
                          ),
                        ),
                      )
                    : null,
                child: _IngredientRow(line: ingredients[i]),
              ),
          ],
        ),
      ),
    );
  }
}

class _IngredientRow extends StatelessWidget {
  const _IngredientRow({required this.line});

  final IngredientLine line;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Row(
      children: <Widget>[
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            color: colorScheme.primary,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            formatIngredientLine(line),
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              fontSize: 14.5,
              color: colorScheme.onSurface,
            ),
          ),
        ),
        if (line.inPantry != null) ...<Widget>[
          const SizedBox(width: 8),
          GleanBadge(
            label: line.inPantry! ? 'in pantry' : 'to buy',
            tone: line.inPantry!
                ? GleanBadgeTone.primary
                : GleanBadgeTone.warning,
          ),
        ],
      ],
    );
  }
}

/// The numbered instructions card.
class InstructionsSection extends StatelessWidget {
  const InstructionsSection({required this.steps, super.key});

  final List<InstructionLine> steps;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            for (int i = 0; i < steps.length; i++)
              Padding(
                padding: EdgeInsets.only(top: i > 0 ? 12 : 0),
                child: _InstructionRow(step: steps[i]),
              ),
          ],
        ),
      ),
    );
  }
}

class _InstructionRow extends StatelessWidget {
  const _InstructionRow({required this.step});

  final InstructionLine step;

  @override
  Widget build(BuildContext context) {
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Container(
          width: 26,
          height: 26,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: colorScheme.primary,
            shape: BoxShape.circle,
          ),
          child: Text(
            '${step.number}',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: colorScheme.onPrimary,
              letterSpacing: 0,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(step.text, style: Theme.of(context).textTheme.bodyLarge),
        ),
      ],
    );
  }
}
