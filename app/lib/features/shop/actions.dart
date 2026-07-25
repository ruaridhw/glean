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
/// `ShoppingRepository.resolveCheckout` guards, per R-03's doc comment on
/// that method). Fires the same light acknowledgement RN used for this tap.
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
///
/// Both the delete and the undo's re-add are guarded (R-07): neither had a
/// `try`/`catch` before, so a DB-layer failure propagated as an uncaught
/// exception with no feedback at all — the same defect class §11 calls
/// "silent failures", already fixed this way in
/// `lib/features/pantry/actions.dart` and `lib/features/meals/actions.dart`.
/// A failed delete leaves the row exactly as it was; a failed undo leaves it
/// deleted, but the user is told rather than left to assume undo worked.
Future<void> deleteShoppingItemWithUndo(
  BuildContext context,
  WidgetRef ref,
  ShoppingListItemView item,
) async {
  final ShoppingRepository repository = ref.read(shoppingRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);

  try {
    await repository.deleteItem(id: item.id, userId: userId);
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
    onUndo: () => unawaited(_restore(context, repository, userId, item)),
  );
}

/// Completes a receipt-less trip (AC-SHOP-02): every checked row is removed
/// via `completeCheckoutWithoutReceipt`, with the same snapshot-and-restore
/// undo [deleteShoppingItemWithUndo] uses, applied to the whole batch. Fires
/// the single `mediumImpact()` for this data commit (AC-HAP-05).
///
/// Guarded the same way as [deleteShoppingItemWithUndo] (R-07): a DB failure
/// here surfaces via `GleanSnackBar` and leaves every checked row exactly as
/// it was, rather than propagating uncaught.
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

  try {
    await repository.completeCheckoutWithoutReceipt(userId: userId);
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
    message: snapshot.length == 1
        ? '1 item checked off'
        : '${snapshot.length} items checked off',
    onUndo: () => unawaited(_restoreAll(context, repository, userId, snapshot)),
  );
}

Future<void> _restore(
  BuildContext context,
  ShoppingRepository repository,
  String userId,
  ShoppingListItemView item,
) async {
  try {
    final int newId = await repository.addManualItem(
      userId: userId,
      name: item.name,
      quantity: item.quantity,
      unit: item.unit,
    );
    if (item.isChecked) {
      await repository.toggleItem(id: newId, userId: userId, checked: true);
    }
  } catch (_) {
    if (context.mounted) {
      GleanSnackBar.show(context, 'Could not restore ${item.name}.');
    }
  }
}

Future<void> _restoreAll(
  BuildContext context,
  ShoppingRepository repository,
  String userId,
  List<ShoppingListItemView> items,
) async {
  for (final ShoppingListItemView item in items) {
    await _restore(context, repository, userId, item);
  }
}
