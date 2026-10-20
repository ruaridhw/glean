import 'package:flutter/material.dart';
import 'package:glean/data/seed/ingredient_groups.dart';
import 'package:glean/design_system/design_system.dart';

import '../intake_presentation.dart';

/// One editable row on the shared intake review screen. Quantity is a free-typed [TextField], not a seed that
/// re-derives itself from a numeric value on every keystroke, which would make decimals untypeable. Validity
/// (and so whether Confirm is enabled) is computed by the parent from the same controller text, never silently
/// defaulted.
class ReviewItemRow extends StatelessWidget {
  const ReviewItemRow({
    super.key,
    required this.nameController,
    required this.quantityController,
    required this.unitController,
    required this.confidence,
    required this.quantityErrorText,
    required this.onRemove,
    this.selectedGroupId,
    this.onGroupChanged,
    this.requiresGroup = false,
  });

  final TextEditingController nameController;
  final TextEditingController quantityController;
  final TextEditingController unitController;
  final double confidence;
  final String? quantityErrorText;
  final VoidCallback onRemove;

  /// The row's chosen ingredient group id, when one is needed.
  final String? selectedGroupId;
  final ValueChanged<String?>? onGroupChanged;

  /// True for a pantry-destined row whose ingredient group came back null: the group is optional, so the row can be
  /// confirmed as is (stored unclassified) or given one here. Shop rows never show it.
  final bool requiresGroup;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final bool flagged = isLowConfidence(confidence);

    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            Row(
              children: <Widget>[
                if (flagged) ...<Widget>[
                  const GleanBadge(
                    label: 'CHECK',
                    tone: GleanBadgeTone.warning,
                  ),
                  SizedBox(width: tokens.spacing.sm),
                ],
                Expanded(
                  child: TextField(
                    controller: nameController,
                    decoration: const InputDecoration(
                      isDense: true,
                      hintText: 'Item name',
                    ),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.close_rounded),
                  tooltip: 'Remove',
                  onPressed: onRemove,
                ),
              ],
            ),
            SizedBox(height: tokens.spacing.sm),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                SizedBox(
                  width: 90,
                  child: GleanField(
                    label: 'Qty',
                    child: TextField(
                      controller: quantityController,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: InputDecoration(
                        isDense: true,
                        // Keep the input's error state; the message below
                        // spans the card instead of this narrow field.
                        error: quantityErrorText == null
                            ? null
                            : const SizedBox.shrink(),
                      ),
                    ),
                  ),
                ),
                SizedBox(width: tokens.spacing.sm),
                SizedBox(
                  width: 90,
                  child: GleanField(
                    label: 'Unit',
                    child: TextField(
                      controller: unitController,
                      decoration: const InputDecoration(isDense: true),
                    ),
                  ),
                ),
              ],
            ),
            if (quantityErrorText != null)
              Padding(
                padding: EdgeInsets.only(
                  top: tokens.spacing.sm,
                  left: tokens.spacing.md,
                  right: tokens.spacing.md,
                ),
                child: Text(
                  quantityErrorText!,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ),
            if (requiresGroup) ...<Widget>[
              SizedBox(height: tokens.spacing.sm),
              GleanField(
                label: 'Ingredient group',
                child: DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: selectedGroupId,
                  decoration: const InputDecoration(
                    isDense: true,
                    helperText:
                        "Optional: we couldn't identify an ingredient group for this item.",
                    helperMaxLines: 2,
                  ),
                  items: <DropdownMenuItem<String>>[
                    for (final IngredientGroupSeed seed in selectableGroupSeeds)
                      DropdownMenuItem<String>(
                        value: seed.id,
                        child: Text(seed.name),
                      ),
                  ],
                  onChanged: onGroupChanged,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
