import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:glean/data/models/meal_plan_entry_view.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/design_system/design_system.dart';

/// The long-press sheet: an optional comment saved with the thumb that was long-pressed.
///
/// Pops the text to save, or `''` when they saved it empty (which clears any earlier note). A Skip or a
/// dismiss pops null, and the caller leaves the entry exactly as it was.
///
/// The sheet fits a small phone at large text: the body scrolls inside the space the keyboard leaves, and the
/// actions wrap onto their own lines rather than overflowing the row width.
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
    final MediaQueryData media = MediaQuery.of(context);
    final bool up = widget.thumb == MealThumb.up;
    // The sheet sits above the keyboard, so only the space the keyboard leaves it is available; the body
    // scrolls inside that rather than pushing the actions off the screen.
    final double available = math.max(
      0,
      media.size.height - media.viewInsets.bottom,
    );

    return Padding(
      padding: EdgeInsets.only(bottom: media.viewInsets.bottom),
      child: SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: available * 0.9),
          child: Padding(
            padding: EdgeInsets.fromLTRB(
              tokens.spacing.lg,
              0,
              tokens.spacing.lg,
              tokens.spacing.lg,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Flexible(
                  child: SingleChildScrollView(
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
                          minLines: 2,
                          maxLines: 3,
                          textCapitalization: TextCapitalization.sentences,
                          // The bound counts code points, the unit the backend counts; Flutter's own
                          // maxLength counts grapheme clusters and would let a combining sequence through.
                          inputFormatters: const <TextInputFormatter>[
                            _RatingNoteFormatter(),
                          ],
                          buildCounter:
                              (
                                BuildContext context, {
                                required int currentLength,
                                required int? maxLength,
                                required bool isFocused,
                              }) => Text(
                                '${ratingNoteLength(_controller.text)}/$maxRatingNoteLength',
                              ),
                          decoration: const InputDecoration(
                            hintText:
                                'Why? (optional) e.g. "too sweet for the kids"',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        SizedBox(height: tokens.spacing.xs),
                        Text(
                          "Saved with your rating. The planner can't read notes yet.",
                          style: textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                ),
                SizedBox(height: tokens.spacing.md),
                // Wrap, not Row: at 320px wide with large text the two buttons no longer fit side by side,
                // and stacking them keeps both reachable and full-size.
                OverflowBar(
                  alignment: MainAxisAlignment.end,
                  overflowAlignment: OverflowBarAlignment.end,
                  spacing: tokens.spacing.sm,
                  overflowSpacing: tokens.spacing.sm,
                  children: <Widget>[
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('Skip'),
                    ),
                    FilledButton(
                      onPressed: () =>
                          Navigator.of(context).pop(_controller.text),
                      child: const Text('Save note'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Caps the field at [maxRatingNoteLength] code points, the unit the backend's `max_length` counts.
///
/// A pasted note is cut back to the bound, keeping whole grapheme clusters so no character is left half
/// written.
class _RatingNoteFormatter extends TextInputFormatter {
  const _RatingNoteFormatter();

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    if (ratingNoteLength(newValue.text) <= maxRatingNoteLength) {
      return newValue;
    }
    final String kept = truncateRatingNote(newValue.text);
    return TextEditingValue(
      text: kept,
      selection: TextSelection.collapsed(offset: kept.length),
      composing: TextRange.empty,
    );
  }
}
