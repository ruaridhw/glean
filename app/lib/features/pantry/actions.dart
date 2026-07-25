/// Pantry mutations shared across the screen and its sheets, mirroring
/// `lib/features/meals/actions.dart`'s pattern — one implementation of
/// delete-with-undo so it behaves identically everywhere.
library;

import 'dart:async' show unawaited;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/pantry_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';

/// Deletes [item] and shows the undo snackbar (AC-UX-02). Does **not** fire
/// a haptic itself — `SwipeToDeleteRow` already fires its one
/// `mediumImpact` on commit (AC-HAP-03, the RN double-buzz bug this port
/// must not reproduce).
///
/// Undo re-adds the item via `PantryRepository.addItem`, which mints a fresh
/// expiry from today's shelf-life default rather than restoring the exact
/// prior expiry date — SQLite has no "undelete at the same row" primitive,
/// and re-inferring is an acceptable (and arguably friendlier — freshly
/// "re-shelved") approximation for a plain delete, unlike "Cooked" undo
/// (AC-UX-03), which has its own exact-reversal path via
/// `cooked_adjustments` because approximating there would be wrong.
///
/// `item.category!`: every pantry row that can exist here was created by
/// `PantryRepository.addItem`, which *requires* a non-null category and
/// upgrades the underlying ingredient's category if it was ever null
/// (`IngredientsRepository._upgradeCategoryIfNeeded`) — so a row reachable
/// from this screen always has one. `PantryItemView.category` stays
/// nullable at the type level only to stay honest about rows inserted
/// outside this repository (FINDINGS.md F-07/F-08), which don't occur via
/// any path this feature exposes.
Future<void> deletePantryItemWithUndo(
  BuildContext context,
  WidgetRef ref,
  PantryItemView item,
) async {
  final repository = ref.read(pantryRepositoryProvider);
  final String userId = ref.read(currentUserIdProvider);

  await repository.deleteItem(id: item.id, userId: userId);
  if (!context.mounted) return;

  GleanSnackBar.showUndo(
    context,
    message: '${item.canonicalName} removed',
    onUndo: () {
      unawaited(
        repository.addItem(
          userId: userId,
          name: item.canonicalName,
          quantity: item.quantity,
          unit: item.unit,
          category: item.category!,
          unitPrice: item.unitPrice,
        ),
      );
    },
  );
}
