import 'package:flutter/material.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/design_system/design_system.dart';

import '../profile_presentation.dart';

/// The notes Glean kept, newest last as stored, each with when and where it came from and a delete.
class ProfileNotesCard extends StatelessWidget {
  const ProfileNotesCard({
    super.key,
    required this.notes,
    required this.onDelete,
  });

  final List<ProfileNote> notes;
  final void Function(int index) onDelete;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme text = Theme.of(context).textTheme;
    return Card(
      child: Padding(
        padding: EdgeInsets.symmetric(vertical: tokens.spacing.sm),
        child: notes.isEmpty
            ? Padding(
                padding: EdgeInsets.symmetric(
                  horizontal: tokens.spacing.md,
                  vertical: tokens.spacing.sm,
                ),
                child: Text(
                  'Nothing yet. When Glean notices something about how you '
                  'eat and you keep it, it shows up here.',
                  style: text.bodyMedium,
                ),
              )
            : Column(
                children: <Widget>[
                  for (final (int index, ProfileNote note) in notes.indexed)
                    Padding(
                      padding: EdgeInsetsDirectional.only(
                        start: tokens.spacing.md,
                        top: tokens.spacing.xs,
                        bottom: tokens.spacing.xs,
                      ),
                      child: Row(
                        children: <Widget>[
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(note.text, style: text.bodyLarge),
                                Text(noteMeta(note), style: text.bodySmall),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Delete note: ${note.text}',
                            icon: const Icon(Icons.close_rounded),
                            onPressed: () => onDelete(index),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}
