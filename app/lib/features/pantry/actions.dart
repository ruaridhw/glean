library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';

/// Undo re-adds via `restoreDeletedItem`, which re-infers expiry from today.
Future<void> deletePantryItemWithUndo(
  BuildContext context,
  WidgetRef ref,
  PantryItemView item,
) {
  final repository = ref.read(pantryRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable<void>(
    context,
    perform: () => repository.deleteItem(id: item.id, userId: userId),
    undo: (_) => repository.restoreDeletedItem(userId: userId, item: item),
    message: '${item.canonicalName} removed',
    failureMessage: 'Could not remove ${item.canonicalName}. Try again.',
    undoFailureMessage: 'Could not restore ${item.canonicalName}.',
  );
}
