import 'package:flutter/material.dart';
import 'package:glean/data/seed/taxonomy.dart';
import 'package:glean/design_system/design_system.dart';

import '../../pantry/pantry_presentation.dart';
import '../intake_presentation.dart';

/// One editable row on the shared intake review screen (AC-PAN-05).
///
/// Quantity is a free-typed [TextField], not a `String(quantity)` seed that
/// re-derives itself from a numeric value on every keystroke — that
/// round-trip is exactly what made decimals untypeable in the RN app (§11,
/// AC-PAN-08). Validity (and therefore whether Confirm is enabled) is
/// computed by the parent from the same controller text, never silently
/// defaulted to `0`/`1` (AC-PAN-09).
class ReviewItemRow extends StatelessWidget {
  const ReviewItemRow({
    super.key,
    required this.nameController,
    required this.quantityController,
    required this.unitController,
    required this.confidence,
    required this.quantityErrorText,
    required this.onRemove,
    this.selectedCategory,
    this.onCategoryChanged,
    this.requiresCategory = false,
  });

  final TextEditingController nameController;
  final TextEditingController quantityController;
  final TextEditingController unitController;
  final double confidence;
  final String? quantityErrorText;
  final VoidCallback onRemove;

  /// The row's chosen taxonomy category, when one is needed.
  final String? selectedCategory;
  final ValueChanged<String?>? onCategoryChanged;

  /// True only for a pantry-destined row whose parsed category came back
  /// null (FINDINGS.md F-07/F-08) — expiry inference has no basis without
  /// one, so this is the one place `PantryRepository.addItem`'s required
  /// category gets supplied for an AI-parsed item. Shop rows never need
  /// this: `ShoppingRepository`'s intake paths accept a null category fine.
  final bool requiresCategory;

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
                  child: TextField(
                    controller: quantityController,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: InputDecoration(
                      isDense: true,
                      labelText: 'Qty',
                      errorText: quantityErrorText,
                    ),
                  ),
                ),
                SizedBox(width: tokens.spacing.sm),
                SizedBox(
                  width: 90,
                  child: TextField(
                    controller: unitController,
                    decoration: const InputDecoration(
                      isDense: true,
                      labelText: 'Unit',
                    ),
                  ),
                ),
              ],
            ),
            if (requiresCategory) ...<Widget>[
              SizedBox(height: tokens.spacing.sm),
              DropdownButtonFormField<String>(
                initialValue: selectedCategory,
                decoration: const InputDecoration(
                  isDense: true,
                  labelText: 'Category',
                  helperText: "We couldn't identify a category for this item.",
                  helperMaxLines: 2,
                ),
                items: <DropdownMenuItem<String>>[
                  for (final CategorySeed seed in ingredientCategorySeeds)
                    DropdownMenuItem<String>(
                      value: seed.category,
                      child: Text(categoryLabel(seed.category)),
                    ),
                ],
                onChanged: onCategoryChanged,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
