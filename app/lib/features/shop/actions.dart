/// Shopping actions preserve complete rows and per-meal ownership on Undo.
library;

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/database.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
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

Future<void> deleteShoppingItemWithUndo(
  BuildContext context,
  WidgetRef ref,
  ShoppingListItemView item,
) async {
  final repository = ref.read(shoppingRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  final messenger = ScaffoldMessenger.of(context);
  final List<ShoppingListItem> snapshot;
  try {
    snapshot = await repository.deleteRowsWithSnapshot(
      ids: item.ids,
      userId: userId,
    );
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(context, 'Could not remove ${item.name}. Try again.');
    }
    return;
  }
  if (!context.mounted) return;
  GleanSnackBar.showUndo(
    context,
    message: '${item.name} removed',
    onUndo: () =>
        unawaited(_restore(messenger, repository, userId, snapshot, item.name)),
  );
}

Future<void> completeCheckoutWithoutReceipt(
  BuildContext context,
  WidgetRef ref,
  List<ShoppingListItemView> checkedItems,
) async {
  final repository = ref.read(shoppingRepositoryProvider);
  final userId = ref.read(currentUserIdProvider);
  final messenger = ScaffoldMessenger.of(context);
  final List<ShoppingListItem> snapshot;
  try {
    snapshot = await repository.deleteCheckedWithSnapshot(userId: userId);
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(context, 'Could not finish shopping. Try again.');
    }
    return;
  }
  ref.read(hapticsProvider).mediumImpact();
  if (!context.mounted) return;
  GleanSnackBar.showUndo(
    context,
    message: checkedItems.length == 1
        ? '1 item checked off'
        : '${checkedItems.length} items checked off',
    onUndo: () => unawaited(
      _restore(messenger, repository, userId, snapshot, 'shopping list'),
    ),
  );
}

Future<void> _restore(
  ScaffoldMessengerState messenger,
  ShoppingRepository repository,
  String userId,
  List<ShoppingListItem> snapshot,
  String label,
) async {
  try {
    await repository.restoreRows(rows: snapshot, userId: userId);
  } catch (_) {
    if (messenger.mounted) {
      GleanSnackBar.showOn(messenger, 'Could not restore $label.');
    }
  }
}
