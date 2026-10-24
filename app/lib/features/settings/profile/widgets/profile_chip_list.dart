import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// One profile list as a card of chips: tap a chip to change it, its ✕ to remove it, and "Add" to add one.
/// [labels] are what the chips say, in list order; the callbacks get the tapped chip's position.
class ProfileChipList extends StatelessWidget {
  const ProfileChipList({
    super.key,
    required this.title,
    required this.labels,
    required this.onAdd,
    required this.onEdit,
    required this.onRemove,
  });

  final String title;
  final List<String> labels;
  final VoidCallback onAdd;
  final void Function(int index) onEdit;
  final void Function(int index) onRemove;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Wrap(
          spacing: tokens.spacing.sm,
          runSpacing: tokens.spacing.sm,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: <Widget>[
            for (final (int index, String label) in labels.indexed)
              ProfileChip(
                label: label,
                onEdit: () => onEdit(index),
                onRemove: () => onRemove(index),
              ),
            ActionChip(
              key: Key('profile.add.$title'),
              avatar: const Icon(Icons.add_rounded),
              label: const Text('Add'),
              tooltip: 'Add to $title',
              onPressed: onAdd,
            ),
          ],
        ),
      ),
    );
  }
}

/// A chip in the theme's chip colours whose ✕ is a full-size icon button, not the small delete area a Material
/// chip gives a short label, so removing is as easy to hit as changing.
class ProfileChip extends StatelessWidget {
  const ProfileChip({
    super.key,
    required this.label,
    required this.onEdit,
    required this.onRemove,
  });

  final String label;
  final VoidCallback onEdit;
  final VoidCallback onRemove;

  /// The remove button and the chip height: a 48pt touch target, the Android guideline (iOS asks 44pt).
  static const double _targetSize = 48;

  @override
  Widget build(BuildContext context) {
    final ChipThemeData chip = ChipTheme.of(context);
    final AppTokens tokens = context.tokens;
    return Material(
      color: chip.backgroundColor,
      shape: const StadiumBorder(),
      clipBehavior: Clip.antiAlias,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Flexible(
            child: Tooltip(
              message: 'Change $label',
              child: InkWell(
                onTap: onEdit,
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: _targetSize),
                  child: Padding(
                    padding: EdgeInsetsDirectional.only(
                      start: tokens.spacing.md,
                      top: tokens.spacing.xs,
                      bottom: tokens.spacing.xs,
                    ),
                    child: Align(
                      widthFactor: 1,
                      alignment: AlignmentDirectional.centerStart,
                      child: Text(label, style: chip.labelStyle),
                    ),
                  ),
                ),
              ),
            ),
          ),
          IconButton(
            tooltip: 'Remove $label',
            onPressed: onRemove,
            iconSize: 18,
            style: IconButton.styleFrom(
              backgroundColor: Colors.transparent,
              foregroundColor: chip.labelStyle?.color,
              fixedSize: const Size.square(_targetSize),
              minimumSize: const Size.square(_targetSize),
            ),
            icon: const Icon(Icons.close_rounded),
          ),
        ],
      ),
    );
  }
}
