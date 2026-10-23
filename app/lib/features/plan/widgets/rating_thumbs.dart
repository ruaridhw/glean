import 'package:flutter/material.dart';
import 'package:glean/data/models/meal_thumb.dart';
import 'package:glean/design_system/design_system.dart';

/// The two thumbs a cooked row carries, replacing the "Cooked?" pill once the meal is done.
///
/// The selected one is filled and tinted; tapping the same thumb again is the caller's business (it
/// clears the rating), and a long-press opens the note sheet for that thumb.
class RatingThumbs extends StatelessWidget {
  const RatingThumbs({
    super.key,
    required this.rating,
    required this.onRate,
    required this.onNote,
  });

  /// The saved thumb, or null while the meal is unrated.
  final MealThumb? rating;
  final ValueChanged<MealThumb> onRate;
  final ValueChanged<MealThumb> onNote;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: <Widget>[
        for (final MealThumb thumb in MealThumb.values)
          Padding(
            padding: EdgeInsets.only(
              left: thumb == MealThumb.values.first ? 0 : 6,
            ),
            child: _ThumbButton(
              thumb: thumb,
              selected: rating == thumb,
              onTap: () => onRate(thumb),
              onLongPress: () => onNote(thumb),
            ),
          ),
      ],
    );
  }
}

class _ThumbButton extends StatelessWidget {
  const _ThumbButton({
    required this.thumb,
    required this.selected,
    required this.onTap,
    required this.onLongPress,
  });

  final MealThumb thumb;
  final bool selected;
  final VoidCallback onTap;
  final VoidCallback onLongPress;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colorScheme = Theme.of(context).colorScheme;
    final bool up = thumb == MealThumb.up;
    final Color tint = selected
        ? (up ? colorScheme.primary : colorScheme.error)
        : colorScheme.onSurfaceVariant;
    final IconData icon = up
        ? (selected ? Icons.thumb_up_alt : Icons.thumb_up_alt_outlined)
        : (selected ? Icons.thumb_down_alt : Icons.thumb_down_alt_outlined);

    return Semantics(
      button: true,
      selected: selected,
      label: up ? 'Thumbs up' : 'Thumbs down',
      child: InkResponse(
        key: Key('rating.${thumb.dbValue}'),
        onTap: onTap,
        onLongPress: onLongPress,
        radius: 24,
        containedInkWell: true,
        child: Container(
          width: 44,
          height: 44,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? tint.withValues(alpha: 0.12) : Colors.transparent,
            border: Border.all(
              color: selected ? tint : colorScheme.outlineVariant,
            ),
            borderRadius: BorderRadius.circular(tokens.radius.md),
          ),
          child: Icon(icon, size: 20, color: tint),
        ),
      ),
    );
  }
}
