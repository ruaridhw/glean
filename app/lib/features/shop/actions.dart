/// Shared shopping-list mutations, each pairing a repository call with the
/// haptic/snackbar behaviour the screen and its rows both need — one
/// implementation so undo and haptics behave identically everywhere a row
/// can be removed (AC-UX-02, AC-HAP-05).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/shopping_repository.dart';
import 'package:glean/design_system/design_system.dart';

/// Toggles [item]'s checked state (AC-SHOP-04's flip side of the ledger — a
/// user tapping a row is always in-scope for that row, so there's no scoping
/// concern here, only for the bulk receipt-driven check-off that
/// `ShoppingRepository.checkOffResolvedIngredients` guards). Fires the same
/// light acknowledgement RN used for this tap.
Future<void> toggleShoppingItem(WidgetRef ref, ShoppingListItemView item) {
  ref.read(hapticsProvider).lightImpact();
  return ref
      .read(shoppingRepositoryProvider)
      .toggleItem(
        id: item.id,
        userId: ref.read(currentUserIdProvider),
        checked: !item.isChecked,
      );
}

/// Deletes [item] and shows the undo snackbar (AC-UX-01/02). Does **not**
/// fire a haptic itself — `SwipeToDeleteRow` already fired the single
/// `mediumImpact()` for the swipe commit (AC-HAP-03, the RN double-buzz bug).
///
/// Undo re-adds the row via [ShoppingRepository.addManualItem] — the same
/// "re-insert a snapshot at a new id" approach `deleteRecipeWithUndo` uses in
/// Meals, since SQLite has no "undelete at the same id" primitive. That
/// entry point re-resolves the same ingredient (it still exists; only the
/// shopping row was deleted) but always inserts as `source: 'manual'`, so an
/// undone plan-derived or AI-parsed row loses its provenance tag. Checked
/// state is preserved with a follow-up `toggleItem` call, since that's a
/// visible behaviour difference an undo really should restore.
Future<void> deleteShoppingItemWithUndo(
  BuildContext context,
  WidgetRef ref,
  ShoppingListItemView item,
) async {
  final ShoppingRepository repository = ref.read(shoppingRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);

  await repository.deleteItem(id: item.id, userId: userId);
  if (!context.mounted) return;

  GleanSnackBar.showUndo(
    context,
    message: '${item.name} removed',
    onUndo: () => unawaited(_restore(repository, userId, item)),
  );
}

/// Completes a receipt-less trip (AC-SHOP-02): every checked row is removed
/// via `completeCheckoutWithoutReceipt`, with the same snapshot-and-restore
/// undo [deleteShoppingItemWithUndo] uses, applied to the whole batch. Fires
/// the single `mediumImpact()` for this data commit (AC-HAP-05).
Future<void> completeCheckoutWithoutReceipt(
  BuildContext context,
  WidgetRef ref,
  List<ShoppingListItemView> checkedItems,
) async {
  final ShoppingRepository repository = ref.read(shoppingRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);
  final List<ShoppingListItemView> snapshot = List<ShoppingListItemView>.of(
    checkedItems,
  );

  await repository.completeCheckoutWithoutReceipt(userId: userId);
  ref.read(hapticsProvider).mediumImpact();
  if (!context.mounted) return;

  GleanSnackBar.showUndo(
    context,
    message: snapshot.length == 1
        ? '1 item checked off'
        : '${snapshot.length} items checked off',
    onUndo: () => unawaited(_restoreAll(repository, userId, snapshot)),
  );
}

Future<void> _restore(
  ShoppingRepository repository,
  String userId,
  ShoppingListItemView item,
) async {
  final int newId = await repository.addManualItem(
    userId: userId,
    name: item.name,
    quantity: item.quantity,
    unit: item.unit,
  );
  if (item.isChecked) {
    await repository.toggleItem(id: newId, userId: userId, checked: true);
  }
}

Future<void> _restoreAll(
  ShoppingRepository repository,
  String userId,
  List<ShoppingListItemView> items,
) async {
  for (final ShoppingListItemView item in items) {
    await _restore(repository, userId, item);
  }
}
