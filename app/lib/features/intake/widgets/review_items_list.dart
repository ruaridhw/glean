import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../review_row.dart';
import 'clarifying_questions_card.dart';
import 'review_item_row.dart';

/// Hints scroll together with editable proposals so multiple questions never
/// squeeze the list off screen or overflow a small phone/keyboard viewport.
class ReviewItemsList extends StatelessWidget {
  const ReviewItemsList({
    super.key,
    required this.rows,
    required this.questions,
    required this.isPantry,
    required this.pending,
    required this.onChanged,
    required this.onRemove,
    this.onAnswer,
  });

  final List<ReviewRow> rows;
  final List<String> questions;
  final bool isPantry;
  final bool pending;
  final VoidCallback onChanged;
  final void Function(int) onRemove;
  final Future<void> Function(Map<String, String>)? onAnswer;

  @override
  Widget build(BuildContext context) {
    if (rows.isEmpty && questions.isEmpty) {
      return const Center(child: Text('Nothing left to review.'));
    }
    final tokens = context.tokens;
    return ListView.separated(
      padding: EdgeInsets.all(tokens.spacing.lg),
      itemCount: rows.length + (questions.isNotEmpty ? 1 : 0),
      separatorBuilder: (context, index) => SizedBox(height: tokens.spacing.sm),
      itemBuilder: (context, index) {
        if (questions.isNotEmpty && index == 0) {
          return ClarifyingQuestionsCard(
            questions: questions,
            pending: pending,
            onSubmit: onAnswer,
          );
        }
        final rowIndex = index - (questions.isNotEmpty ? 1 : 0);
        final row = rows[rowIndex];
        final item = ReviewItemRow(
          key: ValueKey(row.reviewId),
          nameController: row.nameController,
          quantityController: row.quantityController,
          unitController: row.unitController,
          confidence: row.confidence,
          quantityErrorText: row.isActive && row.parsedQuantity == null
              ? 'Enter a quantity greater than 0'
              : null,
          requiresCategory: isPantry && row.category == null,
          selectedCategory: row.category,
          onCategoryChanged: (value) {
            row.category = value;
            onChanged();
          },
          onRemove: () => onRemove(rowIndex),
        );
        return AbsorbPointer(
          absorbing: pending,
          child: isPantry
              ? item
              : Row(
                  children: [
                    Checkbox(
                      value: row.selected,
                      onChanged: (value) {
                        row.selected = value ?? false;
                        onChanged();
                      },
                    ),
                    Expanded(child: item),
                  ],
                ),
        );
      },
    );
  }
}
