/// The shopping list's body: skeleton/error/empty states, then the "to buy" and "in cart" sections of swipe-to-delete
/// rows. Each row fades and slides in once, keyed by item id, so only newly inserted rows animate.
library;

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/design_system/design_system.dart';

import '../actions.dart';
import '../presentation.dart';
import 'shop_states.dart';
import 'shopping_row.dart';

class ShopListSection extends ConsumerWidget {
  const ShopListSection({required this.itemsAsync, super.key});

  final AsyncValue<List<ShoppingListItemView>> itemsAsync;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      child: KeyedSubtree(
        key: ValueKey<bool>(!itemsAsync.hasValue),
        child: !itemsAsync.hasValue
            ? const ListSkeleton(rowHeight: 56, padding: false)
            : itemsAsync.maybeWhen(
                data: (List<ShoppingListItemView> items) => items.isEmpty
                    ? const ShopEmptyState()
                    : _ShopItemsList(items: items),
                orElse: () => const ShopErrorState(),
              ),
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
          _Row(
            key: ValueKey<int>(item.id),
            item: item,
            bottomGap: tokens.spacing.sm,
          ),
        if (inCart.isNotEmpty) ...<Widget>[
          SizedBox(height: tokens.spacing.xs),
          const _SectionHeader(title: inCartSectionTitle),
        ],
        for (final ShoppingListItemView item in inCart)
          _Row(
            key: ValueKey<int>(item.id),
            item: item,
            bottomGap: tokens.spacing.sm,
          ),
      ],
    );
  }
}

class _Row extends ConsumerWidget {
  const _Row({super.key, required this.item, required this.bottomGap});

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
        )
        .animate()
        .fadeIn(duration: 220.ms, curve: Curves.easeOut)
        .slideY(begin: 0.08, end: 0);
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: context.tokens.spacing.sm),
      // Flutter's TextStyle has no text-transform, so the uppercase look is applied explicitly here.
      child: Text(
        title.toUpperCase(),
        style: Theme.of(context).textTheme.labelSmall,
      ),
    );
  }
}
