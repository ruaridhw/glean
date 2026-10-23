import 'package:flutter/material.dart';
import 'package:glean/api/models/meal_plan.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/design_system/design_system.dart';

/// The long-press sheet: an optional comment saved with the thumb that was long-pressed.
///
/// Pops the text to save, or `''` when they saved it empty (which clears any earlier note). A Skip or a
/// dismiss pops null, and the callers leaves the entry exactly as it was.
class RatingNoteSheet extends StatefulWidget {
  const RatingNoteSheet({super.key, required this.entry, required this.thumb});

  final MealPlanEntryView entry;
  final MealThumb thumb;

  @override
  State<RatingNoteSheet> createState() => _RatingNoteSheetState();
}

class _RatingNoteSheetState extends State<RatingNoteSheet> {
  late final TextEditingController _controller = TextEditingController(
    text: widget.entry.note ?? '',
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    final bool up = widget.thumb == MealThumb.up;
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(
          left: tokens.spacing.lg,
          right: tokens.spacing.lg,
          bottom: MediaQuery.viewInsetsOf(context).bottom + tokens.spacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '${up ? 'Thumbs up' : 'Thumbs down'}: ${widget.entry.recipeTitle}',
              style: textTheme.titleMedium,
            ),
            SizedBox(height: tokens.spacing.md),
            TextField(
              key: const Key('rating.note'),
              controller: _controller,
              autofocus: true,
              maxLength: maxRatingNoteLength,
              maxLines: 3,
              minLines: 2,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                hintText: 'Why? (optional) e.g. "too sweet for the kids"',
                border: OutlineInputBorder(),
              ),
            ),
            SizedBox(height: tokens.spacing.xs),
            Text(
              "Saved with your rating. The planner can't read notes yet.",
              style: textTheme.bodySmall,
            ),
            SizedBox(height: tokens.spacing.md),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(context).pop(),
                  child: const Text('Skip'),
                ),
                SizedBox(width: tokens.spacing.sm),
                FilledButton(
                  onPressed: () => Navigator.of(context).pop(_controller.text),
                  child: const Text('Save note'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
