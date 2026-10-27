/// The "Glean noted" card at the top of a proposal: what the planner noticed about the household, one row per
/// note, each with Keep and a dismiss. The screen owns what Keep writes and which notes are handled; this card
/// only draws the notes still waiting, and the screen leaves it out once there are none.
library;

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// The smallest tap target a row action gets.
const double _targetSize = 48;

class GleanNotedCard extends StatelessWidget {
  const GleanNotedCard({
    super.key,
    required this.notes,
    required this.onKeep,
    required this.onDismiss,
    this.keeping = const <String>{},
  });

  /// The notes not yet kept or dismissed, in the planner's order.
  final List<String> notes;

  /// Notes whose Keep is saving; their buttons wait so a double tap cannot keep one twice.
  final Set<String> keeping;
  final ValueChanged<String> onKeep;
  final ValueChanged<String> onDismiss;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    // Not one merged node: a screen reader reads the heading, then each note with its own two actions.
    return Card(
      semanticContainer: false,
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Semantics(
              container: true,
              header: true,
              child: Text('Glean noted', style: theme.textTheme.titleMedium),
            ),
            for (final String note in notes)
              _NoteRow(
                key: ValueKey<String>('glean-noted-$note'),
                note: note,
                keeping: keeping.contains(note),
                onKeep: () => onKeep(note),
                onDismiss: () => onDismiss(note),
              ),
            Text(
              'From your ratings, answers and swap notes. Kept notes go in your profile.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NoteRow extends StatelessWidget {
  const _NoteRow({
    super.key,
    required this.note,
    required this.keeping,
    required this.onKeep,
    required this.onDismiss,
  });

  final String note;
  final bool keeping;
  final VoidCallback onKeep;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Expanded(
          child: Text(note, style: Theme.of(context).textTheme.bodyMedium),
        ),
        TextButton(
          style: TextButton.styleFrom(
            minimumSize: const Size(_targetSize, _targetSize),
          ),
          onPressed: keeping ? null : onKeep,
          child: Text('Keep', semanticsLabel: 'Keep: $note'),
        ),
        IconButton(
          onPressed: keeping ? null : onDismiss,
          // The theme's icon button is a 40 dp filled disc; a row action is a plain 48 dp target.
          style: IconButton.styleFrom(
            backgroundColor: Colors.transparent,
            fixedSize: const Size.square(_targetSize),
            minimumSize: const Size.square(_targetSize),
          ),
          icon: Icon(Icons.close_rounded, semanticLabel: 'Dismiss: $note'),
        ),
      ],
    );
  }
}
