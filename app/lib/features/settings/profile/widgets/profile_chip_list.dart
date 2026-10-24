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
          children: <Widget>[
            for (final (int index, String label) in labels.indexed)
              InputChip(
                label: Text(label),
                tooltip: 'Change $label',
                onPressed: () => onEdit(index),
                onDeleted: () => onRemove(index),
                deleteButtonTooltipMessage: 'Remove $label',
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
