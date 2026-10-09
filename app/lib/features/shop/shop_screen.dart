/// The Shop tab — FLUTTER_MIGRATION.md §6 "Shop". Replaces the Expo app's
/// `app/(tabs)/shop/index.tsx` (see git history).
///
/// The two intake entry points on this screen ("Describe list" and "Scan
/// receipt") both push into the shared intake flow the router already wires
/// (`lib/features/intake/**`, owned by the Pantry+Intake wave) rather than
/// building a second describe/review screen here (§6 — "one review screen,
/// not two"). `ScanArgs.returnToShop`/`ReviewArgs.returnToShop` is how that
/// flow knows to call `ShoppingRepository.resolveCheckout` on confirm
/// instead of a plain pantry commit — see `intake_params.dart`.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth_controller.dart'
    show aiFeaturesAvailableProvider;
import 'package:glean/data/models/shopping_list_item_view.dart';
import 'package:glean/data/providers/shopping_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:glean/router/intake_params.dart';
import 'package:go_router/go_router.dart';

import 'actions.dart';
import 'presentation.dart';
import 'widgets/shop_add_field.dart';
import 'widgets/shop_checkout_bar.dart';
import 'widgets/shop_list_section.dart';

class ShopScreen extends ConsumerStatefulWidget {
  const ShopScreen({super.key});

  @override
  ConsumerState<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends ConsumerState<ShopScreen> {
  // Guards "Done shopping" against a double-tap firing the checkout twice —
  // there's no network call to time out, but the same discipline the
  // add-item flow needs (AC-SHOP-09) applies to any button that commits data.
  bool _completingCheckout = false;

  Future<void> _doneShopping(List<ShoppingListItemView> checkedItems) async {
    if (_completingCheckout) return;
    setState(() => _completingCheckout = true);
    try {
      await completeCheckoutWithoutReceipt(context, ref, checkedItems);
    } finally {
      if (mounted) setState(() => _completingCheckout = false);
    }
  }

  void _scanReceipt() {
    ref.read(hapticsProvider).lightImpact();
    context.pushNamed(
      AppRoutes.intakeScan.name,
      extra: const ScanArgs(returnToShop: true),
    );
  }

  void _describeList() {
    ref.read(hapticsProvider).lightImpact();
    context.pushNamed(AppRoutes.intakeDescribeShop.name);
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final AsyncValue<List<ShoppingListItemView>> itemsAsync = ref.watch(
      shoppingListProvider,
    );
    final List<ShoppingListItemView> items =
        itemsAsync.value ?? const <ShoppingListItemView>[];
    final List<ShoppingListItemView> checkedItems = <ShoppingListItemView>[
      for (final ShoppingListItemView item in items)
        if (item.isChecked) item,
    ];
    final int uncheckedCount = items.length - checkedItems.length;
    // R-08/AC-AUTH-04: both "Describe list" and "Scan receipt" call the AI
    // backend, so both are disabled while a session is expired — the
    // [SignedOutBanner] mounted above every tab is what explains why.
    final bool aiAvailable = ref.watch(aiFeaturesAvailableProvider);

    return Scaffold(
      // AC-SHOP-10: so the keyboard never covers the pinned add field.
      resizeToAvoidBottomInset: true,
      appBar: AppBar(
        title: const Text('Shopping'),
        actions: <Widget>[
          IconButton(
            icon: const Icon(Icons.auto_awesome_rounded),
            tooltip: 'Describe list',
            onPressed: aiAvailable ? _describeList : null,
          ),
        ],
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: <Widget>[
            Expanded(
              child: Padding(
                padding: EdgeInsets.fromLTRB(
                  tokens.spacing.lg,
                  tokens.spacing.md,
                  tokens.spacing.lg,
                  0,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    if (items.isNotEmpty) ...<Widget>[
                      Wrap(
                        spacing: tokens.spacing.sm,
                        children: <Widget>[
                          GleanBadge(
                            label: toBuyCountLabel(uncheckedCount),
                            tone: GleanBadgeTone.primary,
                          ),
                          GleanBadge(
                            label: cartCountLabel(checkedItems.length),
                          ),
                        ],
                      ),
                      SizedBox(height: tokens.spacing.md),
                    ],
                    const ShopAddField(),
                    SizedBox(height: tokens.spacing.md),
                    Expanded(child: ShopListSection(itemsAsync: itemsAsync)),
                  ],
                ),
              ),
            ),
            ShopCheckoutBar(
              checkedCount: checkedItems.length,
              busy: _completingCheckout,
              aiFeaturesAvailable: aiAvailable,
              onScanReceipt: _scanReceipt,
              onDoneShopping: () => _doneShopping(checkedItems),
            ),
          ],
        ),
      ),
    );
  }
}
