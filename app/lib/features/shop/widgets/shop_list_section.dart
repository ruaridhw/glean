/// The shopping list's body: skeleton/error/empty states, then the "to buy"
/// and "in cart" sections (AC-SHOP-07's unified naming) each rendered as
/// swipe-to-delete rows with an animated-closed gap on commit (AC-TRN-02 —
/// inherited free from `Dismissible`, no `AnimatedList` needed; see
/// `MealsScreen`'s identical choice and its comment on why the two would
/// fight each other) and a fade/settle on insertion via [GleanListEntrance]
/// (AC-TRN-02, R-10).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../actions.dart';
import '../presentation.dart';
import 'shop_skeleton.dart';
import 'shop_states.dart';
import 'shopping_row.dart';

class ShopListSection extends ConsumerWidget {
  const ShopListSection({required this.itemsAsync, super.key});

  final AsyncValue<List<ShoppingListItemView>> itemsAsync;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return GleanCrossFade(
      showSkeleton: !itemsAsync.hasValue,
      skeleton: const ShopListSkeleton(),
      content: itemsAsync.maybeWhen(
        data: (List<ShoppingListItemView> items) => items.isEmpty
            ? const ShopEmptyState()
            : _ShopItemsList(items: items),
        orElse: () => const ShopErrorState(),
      ),
    );
  }
}

class _ShopItemsList extends ConsumerWidget {
  const _ShopItemsList({required this.items});

  final List<ShoppingListItemView> items;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AppTokens tokens = context.tokens;
    final List<ShoppingListItemView> toBuy = <ShoppingListItemView>[
      for (final ShoppingListItemView item in items)
        if (!item.isChecked) item,
    ];
    final List<ShoppingListItemView> inCart = <ShoppingListItemView>[
      for (final ShoppingListItemView item in items)
        if (item.isChecked) item,
    ];

    return ListView(
      children: <Widget>[
        if (toBuy.isNotEmpty) const _SectionHeader(title: toBuySectionTitle),
        for (final ShoppingListItemView item in toBuy)
          GleanListEntrance(
            key: ValueKey<int>(item.id),
            child: _Row(item: item, bottomGap: tokens.spacing.sm),
          ),
        if (inCart.isNotEmpty) ...<Widget>[
          SizedBox(height: tokens.spacing.xs),
          const _SectionHeader(title: inCartSectionTitle),
        ],
        for (final ShoppingListItemView item in inCart)
          GleanListEntrance(
            key: ValueKey<int>(item.id),
            child: _Row(item: item, bottomGap: tokens.spacing.sm),
          ),
      ],
    );
  }
}

class _Row extends ConsumerWidget {
  const _Row({required this.item, required this.bottomGap});

  final ShoppingListItemView item;
  final double bottomGap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: EdgeInsets.only(bottom: bottomGap),
      child: SwipeToDeleteRow(
        dismissibleKey: ValueKey<int>(item.id),
        onDelete: () => deleteShoppingItemWithUndo(context, ref, item),
        child: ShoppingRow(
          item: item,
          onToggle: () => toggleShoppingItem(ref, item),
        ),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      // Flutter's TextStyle has no text-transform (FINDINGS.md F-04) — the
      // uppercase look RN got from CSS is applied explicitly here instead.
      child: Text(
        title.toUpperCase(),
        style: Theme.of(context).textTheme.labelSmall,
      ),
    );
  }
}
