library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';

Future<void> toggleShoppingItem(WidgetRef ref, ShoppingListItemView item) {
  ref.read(hapticsProvider).lightImpact();
  return ref
      .read(shoppingRepositoryProvider)
      .toggleRows(
        ids: item.ids,
        userId: ref.read(currentUserIdProvider),
        checked: !item.isChecked,
      );
}

/// Undo restores the complete rows, preserving per-meal ownership.
Future<void> deleteShoppingItemWithUndo(
  BuildContext context,
  WidgetRef ref,
  ShoppingListItemView item,
) {
  final repository = ref.read(shoppingRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable(
    context,
    perform: () =>
        repository.deleteRowsWithSnapshot(ids: item.ids, userId: userId),
    undo: (rows) => repository.restoreRows(rows: rows, userId: userId),
    message: '${item.name} removed',
    failureMessage: 'Could not remove ${item.name}. Try again.',
    undoFailureMessage: 'Could not restore ${item.name}.',
  );
}

Future<void> completeCheckoutWithoutReceipt(
  BuildContext context,
  WidgetRef ref,
  List<ShoppingListItemView> checkedItems,
) {
  final repository = ref.read(shoppingRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  return GleanSnackBar.runUndoable(
    context,
    perform: () => repository.deleteCheckedWithSnapshot(userId: userId),
    undo: (rows) => repository.restoreRows(rows: rows, userId: userId),
    message: checkedItems.length == 1
        ? '1 item checked off'
        : '${checkedItems.length} items checked off',
    failureMessage: 'Could not finish shopping. Try again.',
    undoFailureMessage: 'Could not restore shopping list.',
    onSuccess: ref.read(hapticsProvider).mediumImpact,
  );
}
