library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/providers/shopping_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

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

/// The pantry review pre-filled with the checked Shopping items: name, quantity and unit as listed (a missing
/// quantity counts as one) and the ingredient's category where it has one. Null when nothing is checked.
Future<ReviewArgs?> checkedItemsReviewArgs(WidgetRef ref) async {
  final List<ShoppingListItemView> checked = <ShoppingListItemView>[
    for (final ShoppingListItemView item
        in ref.read(shoppingListProvider).value ??
            const <ShoppingListItemView>[])
      if (item.isChecked) item,
  ];
  if (checked.isEmpty) return null;
  final Map<int, String> categories = await ref
      .read(ingredientsRepositoryProvider)
      .categoriesById(<int>[for (final item in checked) item.ingredientId]);
  return ReviewArgs(
    destination: ReviewDestination.pantry,
    returnToShop: true,
    fromCheckedItems: true,
    items: <ReviewItemDraft>[
      for (final ShoppingListItemView item in checked)
        ReviewItemDraft(
          reviewId: 'checked-${item.id}',
          name: item.name,
          quantity: (item.quantity ?? 0) > 0 ? item.quantity! : 1,
          unit: item.unit ?? '',
          confidence: 1,
          category: categories[item.ingredientId],
          sourceRowIds: item.ids,
        ),
    ],
  );
}

/// "Done shopping": nothing is removed here. The checked rows go through the pantry review, and are cleared
/// (with the pantry additions, under one Undo) only when that review is confirmed.
Future<void> completeCheckoutWithoutReceipt(
  BuildContext context,
  WidgetRef ref,
) async {
  final ReviewArgs? args = await checkedItemsReviewArgs(ref);
  if (args == null || !context.mounted) return;
  ref.read(hapticsProvider).lightImpact();
  await context.pushNamed(AppRoutes.intakeReview.name, extra: args);
}
